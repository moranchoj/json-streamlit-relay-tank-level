#!/usr/bin/env python3
"""
Script de test per simular dades MQTT i provar el funcionament de l'aplicació
"""

import json
import time
import random
from datetime import datetime
import logging

# Mock d'una simulació de nivells per testing
def simulate_tank_levels():
    """Genera nivells simulats per als dipòsits"""
    # Simulació de nivells realistes
    tank_low = random.uniform(10, 25)  # Dipòsit baix entre 10-25%
    tank_high = random.uniform(80, 95)  # Dipòsit alt entre 80-95%
    
    return tank_low, tank_high

def create_test_historic_data():
    """Crea dades d'històric de prova"""
    import pandas as pd
    from datetime import timedelta
    
    # Crear dades de prova per als últims 30 dies
    dates = []
    durations = []
    tank_low_initial = []
    tank_high_initial = []
    tank_low_final = []
    tank_high_final = []
    types = []
    
    base_date = datetime.now() - timedelta(days=30)
    
    for i in range(30):
        current_date = base_date + timedelta(days=i)
        
        # Només crear maniobres alguns dies
        if random.random() < 0.8:  # 80% de probabilitat de maniobra cada dia
            dates.append(current_date.strftime('%Y-%m-%d'))
            durations.append(round(random.uniform(2.5, 3.5), 2))
            tank_low_initial.append(round(random.uniform(18, 25), 1))
            tank_high_initial.append(round(random.uniform(82, 88), 1))
            tank_low_final.append(round(random.uniform(16, 22), 1))
            tank_high_final.append(round(random.uniform(85, 92), 1))
            
            # Tipus de maniobra
            tipo = random.choices(
                ['programada', 'manual', 'manteniment'], 
                weights=[0.7, 0.2, 0.1]
            )[0]
            types.append(tipo)
    
    # Crear DataFrame
    df = pd.DataFrame({
        'Data_Inici': dates,
        'Hora_Inici': ['12:00:00'] * len(dates),
        'Data_Final': dates,
        'Hora_Final': ['12:03:00'] * len(dates),
        'Durada_min': durations,
        'Nivell_Baix_Inicial': tank_low_initial,
        'Nivell_Alt_Inicial': tank_high_initial,
        'Nivell_Baix_Final': tank_low_final,
        'Nivell_Alt_Final': tank_high_final,
        'Tipus_Maniobra': types
    })
    
    # Guardar a CSV
    df.to_csv('historic.csv', sep=';', index=False)
    print(f"✅ Històric de prova creat amb {len(df)} registres")

if __name__ == "__main__":
    print("🧪 Script de Test del Sistema de Control de Bomba")
    print("=" * 50)
    
    # Crear històric de prova
    create_test_historic_data()
    
    # Mostrar nivells simulats
    print("\n📊 Simulació de nivells:")
    for i in range(5):
        low, high = simulate_tank_levels()
        print(f"  Mostra {i+1}: Dipòsit Baix: {low:.1f}%, Dipòsit Alt: {high:.1f}%")
    
    print("\n✅ Test completat. Ara pots:")
    print("  1. Executar 'streamlit run app.py' per veure l'aplicació")
    print("  2. Anar a la pestanya 'Històric' per veure les dades de prova")
    print("  3. Provar els controls manuals")