import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class TrainingNotes:
    """Zarządzanie notatkami do treningów"""

    NOTES_DIR = Path("training_notes")

    def __init__(self):
        self.NOTES_DIR.mkdir(exist_ok=True)

    def get_notes_file(self, training_file):
        """Pobierz plik notatek dla danego treningu"""
        base_name = Path(training_file).stem
        return self.NOTES_DIR / f"{base_name}_notes.json"

    def load_notes(self, training_file):
        """Załaduj notatki z JSON"""
        notes_file = self.get_notes_file(training_file)
        if notes_file.exists():
            try:
                with open(notes_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load notes from {notes_file}: {e}")
                return {"training_file": training_file, "notes": []}
        return {"training_file": training_file, "notes": []}

    def save_notes(self, training_file, notes_data):
        """Zapisz notatki do JSON"""
        notes_file = self.get_notes_file(training_file)
        try:
            with open(notes_file, "w", encoding="utf-8") as f:
                json.dump(notes_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to save notes to {notes_file}: {e}")

    def add_note(self, training_file, time_minute, metric, text):
        """Dodaj notatkę"""
        notes_data = self.load_notes(training_file)

        note = {
            "time_minute": float(time_minute),
            "metric": metric,
            "text": text,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        notes_data["notes"].append(note)
        self.save_notes(training_file, notes_data)
        return note

    def get_notes_for_metric(self, training_file, metric):
        """Pobierz notatki dla konkretnej metryki"""
        notes_data = self.load_notes(training_file)
        return [n for n in notes_data["notes"] if n["metric"] == metric]

    def delete_note(self, training_file, note_index):
        """Usuń notatkę"""
        notes_data = self.load_notes(training_file)
        if 0 <= note_index < len(notes_data["notes"]):
            notes_data["notes"].pop(note_index)
            self.save_notes(training_file, notes_data)
            return True
        return False
