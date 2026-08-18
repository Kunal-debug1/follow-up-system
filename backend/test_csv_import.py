"""Test CSV import functionality."""
import tempfile
from pathlib import Path

# Create a test CSV with standard headers
with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='wb') as f:
    f.write(b'Name,Phone,Email\n')
    f.write(b'Ada,9876543210,ada@example.com\n')
    f.write(b'Bob,8765432109,bob@example.com\n')
    tmpfile = f.name

path = Path(tmpfile)
print(f'Created CSV at: {path}')

# Try analyze_file
from app.services.import_service import analyze_file
analysis = analyze_file(path, 'csv')
print(f'Analysis: {analysis}')

# Try iter_records
from app.services.import_service import iter_records
records = list(iter_records(path, 'csv', None, analysis['detected_mapping']))
print(f'Records: {records}')

path.unlink()
print('Success!')