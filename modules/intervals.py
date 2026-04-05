import pandas as pd


def _resolve_watts_col(df: pd.DataFrame) -> str:
    """Return the name of the watts column to use."""
    return "watts_smooth" if "watts_smooth" in df.columns else "watts"


def _find_raw_intervals(
    df: pd.DataFrame, col_watts: str, threshold_watts: float
) -> list:
    """Detect raw work intervals above threshold and return start/end index pairs."""
    is_work = (df[col_watts] >= threshold_watts).astype(int)

    diffs = is_work.diff()
    starts = diffs[diffs == 1].index
    ends = diffs[diffs == -1].index

    if is_work.iloc[0] == 1:
        starts = starts.insert(0, df.index[0])
    if is_work.iloc[-1] == 1:
        ends = ends.insert(len(ends), df.index[-1])

    if len(starts) == 0:
        return []

    intervals = []
    for s, e in zip(starts, ends, strict=False):
        try:
            idx_s = df.index.get_loc(s)
            idx_e = df.index.get_loc(e)
        except KeyError:
            idx_s = s
            idx_e = e
        intervals.append({"start_idx": idx_s, "end_idx": idx_e})

    return intervals


def _merge_close_intervals(
    intervals: list, df: pd.DataFrame, recovery_time_limit: int
) -> list:
    """Merge intervals separated by less than recovery_time_limit seconds."""
    if not intervals:
        return []

    merged = [intervals[0].copy()]
    for current in intervals[1:]:
        previous = merged[-1]
        t_prev_end = df.iloc[previous["end_idx"]]["time"]
        t_curr_start = df.iloc[current["start_idx"]]["time"]
        gap = t_curr_start - t_prev_end

        if gap <= recovery_time_limit:
            previous["end_idx"] = current["end_idx"]
        else:
            merged.append(current)

    return merged


def _build_interval_stats(
    intervals: list, df: pd.DataFrame, col_watts: str, min_duration: int
) -> list:
    """Filter intervals by min_duration and compute summary statistics."""
    final_results = []
    interval_id = 1

    for interval in intervals:
        s_idx = interval["start_idx"]
        e_idx = interval["end_idx"]
        chunk = df.iloc[s_idx:e_idx]
        duration = chunk["time"].iloc[-1] - chunk["time"].iloc[0]

        if duration < min_duration:
            continue

        stats = {
            "ID": interval_id,
            "Start (min)": round(chunk["time"].iloc[0] / 60, 2),
            "Duration": f"{int(duration // 60)}:{int(duration % 60):02d}",
            "Duration (s)": int(duration),
            "Avg Power": int(chunk[col_watts].mean()),
            "Max Power": int(chunk[col_watts].max()),
            "Avg HR": int(chunk["heartrate"].mean()) if "heartrate" in chunk.columns else 0,
            "Avg Cadence": int(chunk["cadence"].mean()) if "cadence" in chunk.columns else 0,
        }

        if "smo2" in chunk.columns:
            stats["Avg SmO2"] = round(chunk["smo2"].mean(), 1)

        final_results.append(stats)
        interval_id += 1

    return final_results


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
    col_watts = _resolve_watts_col(df)
    if col_watts not in df.columns:
        return pd.DataFrame()

    threshold_watts = cp * min_power_pct

    raw_intervals = _find_raw_intervals(df, col_watts, threshold_watts)
    if not raw_intervals:
        return pd.DataFrame()

    merged = _merge_close_intervals(raw_intervals, df, recovery_time_limit)
    stats = _build_interval_stats(merged, df, col_watts, min_duration)

    return pd.DataFrame(stats)
