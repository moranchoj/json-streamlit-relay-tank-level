#!/usr/bin/env python3
"""
Test script per validar la funcionalitat bàsica del sistema de control de bomba.
"""

import sys
import json
import datetime
from pathlib import Path

# Afegir el directori actual al path per importar app
sys.path.insert(0, str(Path(__file__).parent))

from app import WaterPumpController, TankLevels, ManeuverRecord

def test_config_loading():
    """Test carregada de configuració"""
    print("🧪 Test: Carregada de configuració...")
    try:
        controller = WaterPumpController()
        assert controller.config["mqtt_broker"] == "192.168.1.43"
        assert controller.config["hora_maniobra"] == "12:00"
        assert controller.config["relay3_gpio"] == 6
        assert controller.config["relay4_gpio"] == 5
        print("✅ Configuració carregada correctament")
        return True
    except Exception as e:
        print(f"❌ Error carregant configuració: {e}")
        return False

def test_tank_levels():
    """Test estructura TankLevels"""
    print("\n🧪 Test: Estructura TankLevels...")
    try:
        levels = TankLevels()
        levels.baix = 25.5
        levels.alt = 87.3
        levels.timestamp = datetime.datetime.now()
        
        assert levels.baix == 25.5
        assert levels.alt == 87.3
        assert levels.timestamp is not None
        print("✅ TankLevels funciona correctament")
        return True
    except Exception as e:
        print(f"❌ Error amb TankLevels: {e}")
        return False

def test_maneuver_record():
    """Test estructura ManeuverRecord"""
    print("\n🧪 Test: Estructura ManeuverRecord...")
    try:
        record = ManeuverRecord(
            inici=datetime.datetime.now(),
            tipus="manual",
            nivell_baix_inicial=20.0,
            nivell_alt_inicial=85.0
        )
        
        assert record.tipus == "manual"
        assert record.nivell_baix_inicial == 20.0
        assert record.arrencada == False  # valor per defecte
        print("✅ ManeuverRecord funciona correctament")
        return True
    except Exception as e:
        print(f"❌ Error amb ManeuverRecord: {e}")
        return False

def test_controller_initialization():
    """Test inicialització del controlador"""
    print("\n🧪 Test: Inicialització del controlador...")
    try:
        controller = WaterPumpController()
        
        # Verificar inicialització bàsica
        assert controller.tank_levels is not None
        assert controller.history == []
        assert controller.current_maneuver is None
        assert controller.is_running == False
        assert controller.manual_mode == False
        
        # Verificar que els relés s'han inicialitzat (mock objects)
        assert hasattr(controller, 'relay3')
        assert hasattr(controller, 'relay4')
        
        print("✅ Controlador inicialitzat correctament")
        return True
    except Exception as e:
        print(f"❌ Error inicialitzant controlador: {e}")
        return False

def test_level_checks():
    """Test comprovacions de nivells"""
    print("\n🧪 Test: Comprovacions de nivells...")
    try:
        controller = WaterPumpController()
        
        # Sense dades -> no operació
        assert not controller._check_levels_for_operation()
        assert controller._should_stop_operation()
        
        # Nivells correctes per operació
        controller.tank_levels.baix = 20.0
        controller.tank_levels.alt = 85.0
        assert controller._check_levels_for_operation()
        assert not controller._should_stop_operation()
        
        # Nivells incorrectes
        controller.tank_levels.baix = 10.0  # massa baix
        controller.tank_levels.alt = 95.0
        assert not controller._check_levels_for_operation()
        assert controller._should_stop_operation()
        
        controller.tank_levels.baix = 20.0
        controller.tank_levels.alt = 100.0  # massa alt
        assert not controller._check_levels_for_operation()
        assert controller._should_stop_operation()
        
        print("✅ Comprovacions de nivells funcionen correctament")
        return True
    except Exception as e:
        print(f"❌ Error amb comprovacions de nivells: {e}")
        return False

def test_maneuver_without_levels():
    """Test maniobra sense nivells adequats"""
    print("\n🧪 Test: Maniobra sense nivells adequats...")
    try:
        controller = WaterPumpController()
        
        # Intentar maniobra sense dades de nivells
        result = controller.start_maneuver("manual")
        assert result == False
        assert controller.current_maneuver is None
        assert len(controller.history) == 1
        assert controller.history[0].arrencada == False
        assert controller.history[0].tipus == "manual"
        
        print("✅ Maniobra sense nivells adequats gestionada correctament")
        return True
    except Exception as e:
        print(f"❌ Error amb maniobra sense nivells: {e}")
        return False

def test_maneuver_with_good_levels():
    """Test maniobra amb nivells adequats"""
    print("\n🧪 Test: Maniobra amb nivells adequats...")
    try:
        controller = WaterPumpController()
        
        # Configurar nivells adequats
        controller.tank_levels.baix = 25.0
        controller.tank_levels.alt = 80.0
        
        # Iniciar maniobra
        result = controller.start_maneuver("manual")
        assert result == True
        assert controller.current_maneuver is not None
        assert controller.current_maneuver.tipus == "manual"
        assert controller.current_maneuver.arrencada == True
        assert controller.is_running == True
        
        # Aturar maniobra
        controller.stop_maneuver()
        assert controller.current_maneuver is None
        assert controller.is_running == False
        assert len(controller.history) == 1
        assert controller.history[0].arrencada == True
        
        print("✅ Maniobra amb nivells adequats funciona correctament")
        return True
    except Exception as e:
        print(f"❌ Error amb maniobra amb nivells adequats: {e}")
        return False

def test_status_reporting():
    """Test informació d'estat"""
    print("\n🧪 Test: Informació d'estat...")
    try:
        controller = WaterPumpController()
        status = controller.get_status()
        
        # Verificar estructura de l'estat
        assert "is_running" in status
        assert "manual_mode" in status
        assert "tank_levels" in status
        assert "current_maneuver" in status
        assert "relay3_active" in status
        assert "relay4_active" in status
        assert "history_count" in status
        
        assert status["is_running"] == False
        assert status["history_count"] == 0
        
        print("✅ Informació d'estat funciona correctament")
        return True
    except Exception as e:
        print(f"❌ Error amb informació d'estat: {e}")
        return False

def run_all_tests():
    """Executa tots els tests"""
    print("🚀 Iniciant tests del sistema de control de bomba...\n")
    
    tests = [
        test_config_loading,
        test_tank_levels,
        test_maneuver_record,
        test_controller_initialization,
        test_level_checks,
        test_maneuver_without_levels,
        test_maneuver_with_good_levels,
        test_status_reporting
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test_func.__name__} va fallar amb excepció: {e}")
            failed += 1
    
    print(f"\n📊 Resultats dels tests:")
    print(f"✅ Tests passats: {passed}")
    print(f"❌ Tests fallats: {failed}")
    print(f"📈 Percentatge d'èxit: {(passed/(passed+failed)*100):.1f}%")
    
    if failed == 0:
        print("\n🎉 Tots els tests han passat correctament!")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) han fallat. Revisa els errors.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)