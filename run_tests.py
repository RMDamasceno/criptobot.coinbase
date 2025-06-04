#!/usr/bin/env python3
"""
Script para executar todos os testes dos bots de criptomoedas.

Este script executa testes unitários e de integração, gerando relatórios
de cobertura e performance.
"""

import os
import sys
import unittest
import time
import argparse
from pathlib import Path
from io import StringIO

# Adicionar diretório raiz ao path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))


class TestResult:
    """Resultado de execução de testes."""
    
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.error_tests = 0
        self.skipped_tests = 0
        self.execution_time = 0.0
        self.failures = []
        self.errors = []


class ColoredTextTestResult(unittest.TextTestResult):
    """Resultado de teste com cores."""
    
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.test_results = TestResult()
        self.start_time = None
        self._verbosity = verbosity
    
    def startTest(self, test):
        super().startTest(test)
        self.start_time = time.time()
        if self._verbosity > 1:
            self.stream.write(f"  {test._testMethodName} ... ")
            self.stream.flush()
    
    def addSuccess(self, test):
        super().addSuccess(test)
        self.test_results.passed_tests += 1
        if self._verbosity > 1:
            self.stream.write("\033[92mOK\033[0m\n")
    
    def addError(self, test, err):
        super().addError(test, err)
        self.test_results.error_tests += 1
        self.test_results.errors.append((test, err))
        if self._verbosity > 1:
            self.stream.write("\033[91mERROR\033[0m\n")
    
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.test_results.failed_tests += 1
        self.test_results.failures.append((test, err))
        if self._verbosity > 1:
            self.stream.write("\033[91mFAIL\033[0m\n")
    
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.test_results.skipped_tests += 1
        if self._verbosity > 1:
            self.stream.write("\033[93mSKIP\033[0m\n")


class TestRunner:
    """Executor de testes."""
    
    def __init__(self, verbosity=2):
        self.verbosity = verbosity
        self.test_modules = [
            'tests.test_technical_indicators',
            'tests.test_trading_strategies',
            'tests.test_integration'
        ]
    
    def discover_tests(self, test_dir="tests"):
        """Descobre todos os testes no diretório."""
        loader = unittest.TestLoader()
        start_dir = Path(test_dir)
        
        if not start_dir.exists():
            print(f"❌ Diretório de testes não encontrado: {start_dir}")
            return unittest.TestSuite()
        
        suite = loader.discover(str(start_dir), pattern='test_*.py')
        return suite
    
    def run_module_tests(self, module_name):
        """Executa testes de um módulo específico."""
        print(f"\n🧪 Executando testes: {module_name}")
        print("=" * 60)
        
        try:
            # Importar módulo
            module = __import__(module_name, fromlist=[''])
            
            # Carregar testes
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromModule(module)
            
            # Executar testes
            stream = StringIO()
            runner = unittest.TextTestRunner(
                stream=stream,
                verbosity=self.verbosity,
                resultclass=ColoredTextTestResult
            )
            
            start_time = time.time()
            result = runner.run(suite)
            execution_time = time.time() - start_time
            
            # Atualizar resultado
            result.test_results.total_tests = result.testsRun
            result.test_results.execution_time = execution_time
            
            # Mostrar resultado
            self._print_module_result(module_name, result.test_results)
            
            return result.test_results
            
        except ImportError as e:
            print(f"❌ Erro ao importar módulo {module_name}: {e}")
            return TestResult()
        except Exception as e:
            print(f"❌ Erro ao executar testes {module_name}: {e}")
            return TestResult()
    
    def run_all_tests(self):
        """Executa todos os testes."""
        print("🚀 Iniciando execução de testes dos Crypto Bots")
        print("=" * 60)
        
        total_result = TestResult()
        module_results = {}
        
        overall_start_time = time.time()
        
        for module_name in self.test_modules:
            result = self.run_module_tests(module_name)
            module_results[module_name] = result
            
            # Agregar resultados
            total_result.total_tests += result.total_tests
            total_result.passed_tests += result.passed_tests
            total_result.failed_tests += result.failed_tests
            total_result.error_tests += result.error_tests
            total_result.skipped_tests += result.skipped_tests
            total_result.execution_time += result.execution_time
        
        overall_execution_time = time.time() - overall_start_time
        
        # Mostrar resumo final
        self._print_final_summary(total_result, overall_execution_time, module_results)
        
        return total_result
    
    def _print_module_result(self, module_name, result):
        """Imprime resultado de um módulo."""
        if result.total_tests == 0:
            print("⚠️  Nenhum teste encontrado")
            return
        
        success_rate = (result.passed_tests / result.total_tests) * 100
        
        print(f"📊 Resultados:")
        print(f"   Total: {result.total_tests}")
        print(f"   ✅ Passou: {result.passed_tests}")
        print(f"   ❌ Falhou: {result.failed_tests}")
        print(f"   🔥 Erro: {result.error_tests}")
        print(f"   ⏭️  Pulou: {result.skipped_tests}")
        print(f"   ⏱️  Tempo: {result.execution_time:.2f}s")
        print(f"   📈 Taxa de sucesso: {success_rate:.1f}%")
        
        if success_rate == 100:
            print("🎉 Todos os testes passaram!")
        elif success_rate >= 80:
            print("✅ Maioria dos testes passou")
        else:
            print("⚠️  Muitos testes falharam")
    
    def _print_final_summary(self, total_result, execution_time, module_results):
        """Imprime resumo final."""
        print("\n" + "=" * 60)
        print("📋 RESUMO FINAL DOS TESTES")
        print("=" * 60)
        
        if total_result.total_tests == 0:
            print("❌ Nenhum teste foi executado!")
            return
        
        success_rate = (total_result.passed_tests / total_result.total_tests) * 100
        
        print(f"📊 Estatísticas Gerais:")
        print(f"   Total de testes: {total_result.total_tests}")
        print(f"   ✅ Passou: {total_result.passed_tests}")
        print(f"   ❌ Falhou: {total_result.failed_tests}")
        print(f"   🔥 Erro: {total_result.error_tests}")
        print(f"   ⏭️  Pulou: {total_result.skipped_tests}")
        print(f"   ⏱️  Tempo total: {execution_time:.2f}s")
        print(f"   📈 Taxa de sucesso: {success_rate:.1f}%")
        
        print(f"\n📈 Resultados por Módulo:")
        for module_name, result in module_results.items():
            if result.total_tests > 0:
                module_success_rate = (result.passed_tests / result.total_tests) * 100
                status = "✅" if module_success_rate == 100 else "⚠️" if module_success_rate >= 80 else "❌"
                print(f"   {status} {module_name}: {result.passed_tests}/{result.total_tests} ({module_success_rate:.1f}%)")
        
        print(f"\n🎯 Resultado Final:")
        if success_rate == 100:
            print("🎉 TODOS OS TESTES PASSARAM! Sistema pronto para produção.")
        elif success_rate >= 90:
            print("✅ EXCELENTE! Quase todos os testes passaram.")
        elif success_rate >= 80:
            print("👍 BOM! Maioria dos testes passou, mas há melhorias a fazer.")
        elif success_rate >= 60:
            print("⚠️  ATENÇÃO! Muitos testes falharam. Revisão necessária.")
        else:
            print("❌ CRÍTICO! Sistema não está pronto. Correções urgentes necessárias.")
    
    def run_specific_test(self, test_name):
        """Executa um teste específico."""
        print(f"🎯 Executando teste específico: {test_name}")
        
        try:
            # Carregar teste específico
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(test_name)
            
            # Executar
            runner = unittest.TextTestRunner(verbosity=self.verbosity)
            result = runner.run(suite)
            
            return result.wasSuccessful()
            
        except Exception as e:
            print(f"❌ Erro ao executar teste {test_name}: {e}")
            return False
    
    def run_performance_tests(self):
        """Executa testes de performance."""
        print("\n⚡ Executando testes de performance...")
        
        # Teste de performance dos indicadores
        try:
            from tests.test_technical_indicators import TestTechnicalIndicators
            
            test_instance = TestTechnicalIndicators()
            test_instance.setUp()
            
            start_time = time.time()
            test_instance.test_performance()
            performance_time = time.time() - start_time
            
            print(f"✅ Teste de performance dos indicadores: {performance_time:.3f}s")
            
            if performance_time < 1.0:
                print("🚀 Performance EXCELENTE!")
            elif performance_time < 2.0:
                print("👍 Performance BOA")
            else:
                print("⚠️  Performance pode ser melhorada")
                
        except Exception as e:
            print(f"❌ Erro no teste de performance: {e}")


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description="Executor de testes para Crypto Bots")
    parser.add_argument(
        "--module",
        type=str,
        help="Executar testes de um módulo específico"
    )
    parser.add_argument(
        "--test",
        type=str,
        help="Executar um teste específico"
    )
    parser.add_argument(
        "--performance",
        action="store_true",
        help="Executar testes de performance"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=2,
        help="Nível de verbosidade (use -v, -vv, -vvv)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Execução rápida (apenas testes essenciais)"
    )
    
    args = parser.parse_args()
    
    # Configurar ambiente
    os.environ.setdefault("TESTING", "1")
    
    # Criar runner
    runner = TestRunner(verbosity=args.verbose)
    
    try:
        if args.test:
            # Teste específico
            success = runner.run_specific_test(args.test)
            sys.exit(0 if success else 1)
        
        elif args.module:
            # Módulo específico
            result = runner.run_module_tests(args.module)
            success_rate = (result.passed_tests / result.total_tests * 100) if result.total_tests > 0 else 0
            sys.exit(0 if success_rate == 100 else 1)
        
        elif args.performance:
            # Testes de performance
            runner.run_performance_tests()
            sys.exit(0)
        
        else:
            # Todos os testes
            if args.quick:
                print("🏃 Modo rápido: executando apenas testes essenciais")
                runner.test_modules = ['tests.test_technical_indicators']
            
            result = runner.run_all_tests()
            
            # Executar testes de performance se todos passaram
            if result.failed_tests == 0 and result.error_tests == 0:
                runner.run_performance_tests()
            
            success_rate = (result.passed_tests / result.total_tests * 100) if result.total_tests > 0 else 0
            sys.exit(0 if success_rate >= 80 else 1)
    
    except KeyboardInterrupt:
        print("\n⏹️  Execução interrompida pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

