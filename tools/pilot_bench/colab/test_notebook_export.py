"""Extract the export cell of the Colab notebook and write a runnable copy for a local clean-venv test.
usage: python test_notebook_export.py OUT_SCRIPT OUT_DIR"""
import json
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
nb = json.loads((here / "caveat_nhts_colab.ipynb").read_text(encoding="utf-8"))
cell = next(c for c in nb["cells"] if "".join(c["source"]).startswith("%%writefile /content/export_inputs.py"))
text = "".join(cell["source"][1:])
text = text.replace("/content/pb", str(here.parent).replace("\\", "/")).replace("/content/caveat_run", sys.argv[2].replace("\\", "/"))
Path(sys.argv[1]).write_text(text, encoding="utf-8")
print("wrote", sys.argv[1])
