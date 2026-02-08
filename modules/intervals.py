import pandas as pd

def detect_intervals(df, cp, min_duration=30, min_power_pct=0.9, recovery_time_limit=30):
    """
    Wykrywa interwały pracy na podstawie progu mocy.
    
    Args:
        df (pd.DataFrame): DataFrame z kolumną 'watts' (lub 'watts_smooth') i 'time'.
        cp (float): Moc Krytyczna (CP) zawodnika.
        min_duration (int): Minimalny czas trwania interwału w sekundach (domyślnie 30s).
        min_power_pct (float): Próg mocy jako % CP (domyślnie 90% CP).
        recovery_time_limit (int): Maksymalna przerwa (w sekundach), którą ignorujemy i 
                                   łączymy dwa interwały w jeden (np. krótkie odpuszczenie).

    Returns:
        pd.DataFrame: Tabela z wykrytymi interwałami (Start, End, Avg Power, Avg HR, Duration).
    """
    
    # 1. Sprawdzenie kolumn
    col_watts = 'watts_smooth' if 'watts_smooth' in df.columns else 'watts'
    if col_watts not in df.columns:
        return pd.DataFrame()
        
    threshold_watts = cp * min_power_pct
    
    # 2. Logika binarna: 1 gdzie moc > próg, 0 gdzie mniej
    is_work = (df[col_watts] >= threshold_watts).astype(int)
    
    # 3. Wykrywanie zmian (krawędzi)
    # diff() daje 1 na początku interwału, -1 na końcu
    diffs = is_work.diff()
    
    starts = diffs[diffs == 1].index
    ends = diffs[diffs == -1].index
    
    # Obsługa brzegowa (jeśli zaczynamy od pracy lub kończymy pracą)
    if is_work.iloc[0] == 1:
        starts = starts.insert(0, df.index[0])
    if is_work.iloc[-1] == 1:
        ends = ends.insert(len(ends), df.index[-1])
        
    # Upewnienie się, że mamy pary
    if len(starts) == 0:
        return pd.DataFrame()
        
    # 4. Tworzenie listy kandydatów
    intervals = []
    
    # Konwersja indeksów na pozycje całkowite (jeśli indeks jest DateTime)
    # Zakładamy, że df jest zresetowany lub dostęp po iloc
    
    for s, e in zip(starts, ends):
        # Pobieramy rzeczywiste czasy (lub indeksy numeryczne jeśli to array)
        # s i e to indeksy w DF
        
        # Jeśli indeks to timedelta/datetime, musimy być ostrożni. 
        # Najlepiej operować na df.iloc[idx]
        
        # Znajdźmy pozycje integer
        try:
            idx_s = df.index.get_loc(s)
            idx_e = df.index.get_loc(e)
        except KeyError:
            # Fallback jeśli indeksy są unikalne
            idx_s = s
            idx_e = e

        intervals.append({'start_idx': idx_s, 'end_idx': idx_e})
        
    # 5. Łączenie bliskich interwałów (Logic: jeśli przerwa < recovery_time_limit)
    if not intervals: return pd.DataFrame()
    
    merged_intervals = [intervals[0]]
    
    for current in intervals[1:]:
        previous = merged_intervals[-1]
        
        # Czas przerwy: start current - end previous
        # Używamy czasu w sekundach z kolumny 'time'
        t_prev_end = df.iloc[previous['end_idx']]['time']
        t_curr_start = df.iloc[current['start_idx']]['time']
        gap = t_curr_start - t_prev_end
        
        if gap <= recovery_time_limit:
            # Połącz
            previous['end_idx'] = current['end_idx']
        else:
            merged_intervals.append(current)
            
    # 6. Filtracja i Obliczanie Statystyk
    final_results = []
    
    interval_id = 1
    
    for interval in merged_intervals:
        s_idx = interval['start_idx']
        e_idx = interval['end_idx']
        
        chunk = df.iloc[s_idx:e_idx]
        
        duration = chunk['time'].iloc[-1] - chunk['time'].iloc[0]
        
        if duration >= min_duration:
            stats = {
                'ID': interval_id,
                'Start (min)': round(chunk['time'].iloc[0] / 60, 2),
                'Duration': f"{int(duration // 60)}:{int(duration % 60):02d}",
                'Duration (s)': int(duration),
                'Avg Power': int(chunk[col_watts].mean()),
                'Max Power': int(chunk[col_watts].max()),
                'Avg HR': int(chunk['heartrate'].mean()) if 'heartrate' in chunk.columns else 0,
                'Avg Cadence': int(chunk['cadence'].mean()) if 'cadence' in chunk.columns else 0
            }
            
            # SmO2 jeśli jest
            if 'smo2' in chunk.columns:
                stats['Avg SmO2'] = round(chunk['smo2'].mean(), 1)
                
            final_results.append(stats)
            interval_id += 1
            
    return pd.DataFrame(final_results)
