from app.data.loader import initialize_database, load_dataset
from pathlib import Path
initialize_database()
load_dataset(Path('data/fordgobike_cleaned.csv'))