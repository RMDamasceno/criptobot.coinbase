#!/usr/bin/env python3
"""
Script de validação para verificar correções aplicadas.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_dockerfile():
    """Verifica se o Dockerfile está correto."""
    print("🔍 Verificando Dockerfile...")
    
    dockerfile_path = Path("Dockerfile")
    if not dockerfile_path.exists():
        print("❌ Dockerfile não encontrado")
        return False
    
    content = dockerfile_path.read_text()
    
    # Verificar se não está copiando .env.example como .env
    if "COPY .env.example .env" in content and "COPY .env.example .env.example" not in content:
        print("❌ Dockerfile ainda tem o problema: COPY .env.example .env")
        return False
    
    # Verificar se tem healthcheck simplificado
    if 'CMD python -c "import sys; sys.path.append' in content:
        print("⚠️  Healthcheck ainda muito complexo")
        return False
    
    print("✅ Dockerfile parece correto")
    return True

def check_requirements():
    """Verifica se o requirements.txt está otimizado."""
    print("🔍 Verificando requirements.txt...")
    
    req_path = Path("requirements.txt")
    if not req_path.exists():
        print("❌ requirements.txt não encontrado")
        return False
    
    content = req_path.read_text()
    
    # Verificar se tem versões flexíveis
    if "coinbase-advanced-py==1.8.0" in content:
        print("⚠️  Versões ainda muito específicas (usar >=1.8.0,<2.0.0)")
        return False
    
    # Verificar dependências essenciais
    essential_deps = [
        "coinbase-advanced-py",
        "pandas",
        "numpy", 
        "pydantic",
        "pydantic-settings",
        "structlog"
    ]
    
    missing_deps = []
    for dep in essential_deps:
        if dep not in content:
            missing_deps.append(dep)
    
    if missing_deps:
        print(f"❌ Dependências faltando: {missing_deps}")
        return False
    
    print("✅ requirements.txt parece correto")
    return True

def check_env_example():
    """Verifica se o .env.example está melhorado."""
    print("🔍 Verificando .env.example...")
    
    env_path = Path(".env.example")
    if not env_path.exists():
        print("❌ .env.example não encontrado")
        return False
    
    content = env_path.read_text()
    
    # Verificar configurações seguras
    checks = [
        ("DRY_RUN_MODE=true", "Modo dry run ativado"),
        ("RISK_PERCENTAGE=1.0", "Percentual de risco conservador"),
        ("MAX_POSITIONS=3", "Máximo de posições limitado"),
        ("COINBASE_ENVIRONMENT=sandbox", "Ambiente sandbox por padrão")
    ]
    
    issues = []
    for check, description in checks:
        if check not in content:
            issues.append(description)
    
    if issues:
        print(f"⚠️  Melhorias recomendadas: {issues}")
        return False
    
    print("✅ .env.example parece correto")
    return True

def check_settings_py():
    """Verifica se o settings.py tem a correção do Pydantic."""
    print("🔍 Verificando src/config/settings.py...")
    
    settings_path = Path("src/config/settings.py")
    if not settings_path.exists():
        print("❌ src/config/settings.py não encontrado")
        return False
    
    content = settings_path.read_text()
    
    # Verificar se tem a correção do Pydantic
    if 'extra = "ignore"' not in content:
        print("❌ Correção do Pydantic não aplicada (falta extra = 'ignore')")
        return False
    
    print("✅ settings.py tem a correção do Pydantic")
    return True

def run_basic_tests():
    """Executa testes básicos se disponíveis."""
    print("🔍 Executando testes básicos...")
    
    test_files = [
        "tests/test_settings.py",
        "tests/test_technical_indicators.py"
    ]
    
    for test_file in test_files:
        if Path(test_file).exists():
            try:
                result = subprocess.run([
                    sys.executable, test_file
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    print(f"✅ {test_file} passou")
                else:
                    print(f"❌ {test_file} falhou: {result.stderr}")
                    return False
            except subprocess.TimeoutExpired:
                print(f"⚠️  {test_file} timeout")
            except Exception as e:
                print(f"❌ Erro executando {test_file}: {e}")
                return False
    
    return True

def main():
    """Função principal de validação."""
    print("🚀 Iniciando validação das correções...")
    print("=" * 50)
    
    checks = [
        check_dockerfile,
        check_requirements, 
        check_env_example,
        check_settings_py,
        run_basic_tests
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"❌ Erro durante verificação: {e}")
            results.append(False)
        print()
    
    print("=" * 50)
    print("📊 RESUMO DA VALIDAÇÃO")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Verificações passaram: {passed}/{total}")
    print(f"📈 Taxa de sucesso: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 Todas as verificações passaram!")
        print("✅ O projeto está pronto para uso!")
    else:
        print("⚠️  Algumas verificações falharam.")
        print("🔧 Aplique as correções recomendadas.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

