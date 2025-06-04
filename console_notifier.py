"""
Sistema de notificações para sinais de trading.

Este módulo implementa diferentes tipos de notificadores para enviar
alertas quando sinais importantes são detectados.
"""

import json
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from ...config.settings import get_settings
from ...config.logging_config import get_logger
from ...core.exceptions import NotificationException, NotificationDeliveryException

logger = get_logger(__name__)


class BaseNotifier(ABC):
    """Classe base para notificadores."""
    
    def __init__(self, enabled: bool = True):
        """
        Inicializa o notificador.
        
        Args:
            enabled: Se o notificador está habilitado
        """
        self.enabled = enabled
        self.settings = get_settings()
    
    @abstractmethod
    def send(self, message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Envia uma notificação.
        
        Args:
            message: Mensagem da notificação
            data: Dados adicionais
            
        Returns:
            True se enviado com sucesso
        """
        pass
    
    def format_signal_message(self, signal_data: Dict[str, Any]) -> str:
        """
        Formata uma mensagem de sinal.
        
        Args:
            signal_data: Dados do sinal
            
        Returns:
            Mensagem formatada
        """
        symbol = signal_data.get('symbol', 'UNKNOWN')
        signal_type = signal_data.get('sinal', 'UNKNOWN')
        confidence = signal_data.get('confianca', {}).get('valor', 0)
        trend = signal_data.get('tendencia', {}).get('direcao', 'indefinida')
        
        message = f"🚨 SINAL DE TRADING 🚨\n"
        message += f"Par: {symbol}\n"
        message += f"Sinal: {signal_type.upper()}\n"
        message += f"Confiança: {confidence}%\n"
        message += f"Tendência: {trend}\n"
        message += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message


class ConsoleNotifier(BaseNotifier):
    """Notificador para console."""
    
    def __init__(self, enabled: bool = True):
        """Inicializa o notificador de console."""
        super().__init__(enabled)
        logger.info("Console notifier initialized", enabled=enabled)
    
    def send(self, message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Envia notificação para o console.
        
        Args:
            message: Mensagem da notificação
            data: Dados adicionais
            
        Returns:
            True se enviado com sucesso
        """
        if not self.enabled:
            return False
        
        try:
            print(f"\n{'='*50}")
            print(f"NOTIFICAÇÃO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*50}")
            print(message)
            if data:
                print(f"\nDados adicionais:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            print(f"{'='*50}\n")
            
            logger.info("Console notification sent", message_length=len(message))
            return True
            
        except Exception as e:
            logger.error("Failed to send console notification", error=str(e))
            return False


class FileNotifier(BaseNotifier):
    """Notificador para arquivo."""
    
    def __init__(self, file_path: Optional[str] = None, enabled: bool = True):
        """
        Inicializa o notificador de arquivo.
        
        Args:
            file_path: Caminho do arquivo de notificações
            enabled: Se o notificador está habilitado
        """
        super().__init__(enabled)
        self.file_path = file_path or self.settings.notification_file_path
        
        # Criar diretório se não existir
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("File notifier initialized", file_path=self.file_path, enabled=enabled)
    
    def send(self, message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Envia notificação para arquivo.
        
        Args:
            message: Mensagem da notificação
            data: Dados adicionais
            
        Returns:
            True se enviado com sucesso
        """
        if not self.enabled:
            return False
        
        try:
            timestamp = datetime.now().isoformat()
            
            notification_entry = {
                "timestamp": timestamp,
                "message": message,
                "data": data or {}
            }
            
            with open(self.file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(notification_entry, ensure_ascii=False) + '\n')
            
            logger.info("File notification sent", file_path=self.file_path)
            return True
            
        except Exception as e:
            logger.error("Failed to send file notification", error=str(e), file_path=self.file_path)
            return False


class WebhookNotifier(BaseNotifier):
    """Notificador para webhook."""
    
    def __init__(self, webhook_url: Optional[str] = None, enabled: bool = True):
        """
        Inicializa o notificador de webhook.
        
        Args:
            webhook_url: URL do webhook
            enabled: Se o notificador está habilitado
        """
        super().__init__(enabled)
        self.webhook_url = webhook_url or self.settings.webhook_url
        
        if not self.webhook_url and enabled:
            logger.warning("Webhook URL not configured, disabling webhook notifier")
            self.enabled = False
        
        logger.info("Webhook notifier initialized", webhook_url=self.webhook_url, enabled=self.enabled)
    
    def send(self, message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Envia notificação via webhook.
        
        Args:
            message: Mensagem da notificação
            data: Dados adicionais
            
        Returns:
            True se enviado com sucesso
        """
        if not self.enabled or not self.webhook_url:
            return False
        
        try:
            payload = {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "data": data or {}
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            response.raise_for_status()
            
            logger.info("Webhook notification sent", status_code=response.status_code)
            return True
            
        except Exception as e:
            logger.error("Failed to send webhook notification", error=str(e), webhook_url=self.webhook_url)
            return False


class SlackNotifier(BaseNotifier):
    """Notificador para Slack."""
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        channel: Optional[str] = None,
        enabled: bool = True
    ):
        """
        Inicializa o notificador do Slack.
        
        Args:
            bot_token: Token do bot do Slack
            channel: Canal do Slack
            enabled: Se o notificador está habilitado
        """
        super().__init__(enabled)
        self.bot_token = bot_token or self.settings.slack_bot_token
        self.channel = channel or self.settings.slack_channel
        
        if not self.bot_token and enabled:
            logger.warning("Slack bot token not configured, disabling Slack notifier")
            self.enabled = False
        
        logger.info("Slack notifier initialized", channel=self.channel, enabled=self.enabled)
    
    def send(self, message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Envia notificação para o Slack.
        
        Args:
            message: Mensagem da notificação
            data: Dados adicionais
            
        Returns:
            True se enviado com sucesso
        """
        if not self.enabled or not self.bot_token:
            return False
        
        try:
            # Formatar mensagem para Slack
            slack_message = f"```\n{message}\n```"
            
            if data:
                slack_message += f"\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"
            
            payload = {
                "channel": self.channel,
                "text": slack_message,
                "username": "Crypto Bot",
                "icon_emoji": ":robot_face:"
            }
            
            headers = {
                "Authorization": f"Bearer {self.bot_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                "https://slack.com/api/chat.postMessage",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            result = response.json()
            
            if not result.get("ok"):
                raise Exception(f"Slack API error: {result.get('error', 'Unknown error')}")
            
            logger.info("Slack notification sent", channel=self.channel)
            return True
            
        except Exception as e:
            logger.error("Failed to send Slack notification", error=str(e), channel=self.channel)
            return False


class DiscordNotifier(BaseNotifier):
    """Notificador para Discord."""
    
    def __init__(self, webhook_url: Optional[str] = None, enabled: bool = True):
        """
        Inicializa o notificador do Discord.
        
        Args:
            webhook_url: URL do webhook do Discord
            enabled: Se o notificador está habilitado
        """
        super().__init__(enabled)
        self.webhook_url = webhook_url or self.settings.discord_webhook_url
        
        if not self.webhook_url and enabled:
            logger.warning("Discord webhook URL not configured, disabling Discord notifier")
            self.enabled = False
        
        logger.info("Discord notifier initialized", webhook_url=self.webhook_url, enabled=self.enabled)
    
    def send(self, message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Envia notificação para o Discord.
        
        Args:
            message: Mensagem da notificação
            data: Dados adicionais
            
        Returns:
            True se enviado com sucesso
        """
        if not self.enabled or not self.webhook_url:
            return False
        
        try:
            # Formatar mensagem para Discord
            discord_message = f"```\n{message}\n```"
            
            if data:
                discord_message += f"\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"
            
            payload = {
                "content": discord_message,
                "username": "Crypto Bot",
                "avatar_url": "https://cdn.discordapp.com/emojis/123456789.png"  # URL do avatar opcional
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            response.raise_for_status()
            
            logger.info("Discord notification sent")
            return True
            
        except Exception as e:
            logger.error("Failed to send Discord notification", error=str(e))
            return False


class NotificationManager:
    """Gerenciador de notificações."""
    
    def __init__(self):
        """Inicializa o gerenciador de notificações."""
        self.settings = get_settings()
        self.notifiers: List[BaseNotifier] = []
        
        # Inicializar notificadores baseado nas configurações
        if self.settings.enable_console_notifications:
            self.notifiers.append(ConsoleNotifier())
        
        if self.settings.enable_file_notifications:
            self.notifiers.append(FileNotifier())
        
        if self.settings.enable_webhook_notifications:
            self.notifiers.append(WebhookNotifier())
        
        if self.settings.enable_slack_notifications:
            self.notifiers.append(SlackNotifier())
        
        if self.settings.enable_discord_notifications:
            self.notifiers.append(DiscordNotifier())
        
        logger.info("Notification manager initialized", notifiers_count=len(self.notifiers))
    
    def send_signal_notification(self, symbol: str, signal_data: Dict[str, Any]) -> bool:
        """
        Envia notificação de sinal.
        
        Args:
            symbol: Símbolo do par de trading
            signal_data: Dados do sinal
            
        Returns:
            True se pelo menos uma notificação foi enviada
        """
        if not self.notifiers:
            logger.warning("No notifiers configured")
            return False
        
        # Verificar nível de notificação
        confidence = signal_data.get('confianca', {}).get('valor', 0)
        signal_type = signal_data.get('sinal', 'hold')
        
        should_notify = False
        
        if self.settings.notification_level.value == "all":
            should_notify = True
        elif self.settings.notification_level.value == "important":
            should_notify = confidence >= 60 or signal_type in ["buy", "sell"]
        elif self.settings.notification_level.value == "critical":
            should_notify = confidence >= 80 or signal_type in ["strong_buy", "strong_sell"]
        
        if not should_notify:
            logger.debug("Signal does not meet notification threshold", confidence=confidence, signal=signal_type)
            return False
        
        # Preparar dados completos
        notification_data = {
            "symbol": symbol,
            **signal_data
        }
        
        # Formatar mensagem
        message = self._format_signal_message(symbol, signal_data)
        
        # Enviar para todos os notificadores
        success_count = 0
        for notifier in self.notifiers:
            try:
                if notifier.send(message, notification_data):
                    success_count += 1
            except Exception as e:
                logger.error(
                    "Notifier failed",
                    notifier_type=type(notifier).__name__,
                    error=str(e)
                )
        
        logger.info(
            "Signal notification sent",
            symbol=symbol,
            signal=signal_type,
            confidence=confidence,
            notifiers_success=success_count,
            notifiers_total=len(self.notifiers)
        )
        
        return success_count > 0
    
    def _format_signal_message(self, symbol: str, signal_data: Dict[str, Any]) -> str:
        """
        Formata mensagem de sinal.
        
        Args:
            symbol: Símbolo do par
            signal_data: Dados do sinal
            
        Returns:
            Mensagem formatada
        """
        signal_type = signal_data.get('sinal', 'UNKNOWN')
        confidence = signal_data.get('confianca', {}).get('valor', 0)
        trend = signal_data.get('tendencia', {}).get('direcao', 'indefinida')
        trend_strength = signal_data.get('tendencia', {}).get('forca', {}).get('valor', 0)
        
        # Emoji baseado no sinal
        if signal_type in ["buy", "strong_buy"]:
            emoji = "🟢"
        elif signal_type in ["sell", "strong_sell"]:
            emoji = "🔴"
        else:
            emoji = "🟡"
        
        message = f"{emoji} SINAL DE TRADING {emoji}\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"📊 Par: {symbol}\n"
        message += f"🎯 Sinal: {signal_type.upper()}\n"
        message += f"🎲 Confiança: {confidence}%\n"
        message += f"📈 Tendência: {trend} ({trend_strength}%)\n"
        message += f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # Adicionar detalhes dos indicadores se disponíveis
        indicators = signal_data.get('indicadores', {})
        if indicators:
            message += f"\n\n📋 INDICADORES:\n"
            for name, details in indicators.items():
                message += f"• {name}: "
                if isinstance(details, dict):
                    if 'valor' in details:
                        message += f"{details['valor']}"
                    elif 'status' in details:
                        message += f"{details['status']}"
                    else:
                        message += f"{details}"
                else:
                    message += f"{details}"
                message += "\n"
        
        return message
    
    def send_custom_notification(self, message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Envia notificação customizada.
        
        Args:
            message: Mensagem da notificação
            data: Dados adicionais
            
        Returns:
            True se pelo menos uma notificação foi enviada
        """
        success_count = 0
        for notifier in self.notifiers:
            try:
                if notifier.send(message, data):
                    success_count += 1
            except Exception as e:
                logger.error(
                    "Notifier failed",
                    notifier_type=type(notifier).__name__,
                    error=str(e)
                )
        
        return success_count > 0

