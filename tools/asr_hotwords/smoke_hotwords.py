import sys
from pathlib import Path
import soundfile as sf
sys.path.insert(0, str(Path(__file__).parent))
from common import recognizer, decode
d = Path(sys.argv[1]); x, sr = sf.read(sys.argv[2], dtype="float32")
rec = recognizer(d, "modified_beam_search", score=float(sys.argv[3]) if len(sys.argv) > 3 else 1.5)
for hw in [None, "Клава Кока/Шоколадница/Европа Плюс/Яндекс Маркет", "Kotlin/Nemotron/sherpa-onnx/Гималаи"]:
    print(hw, "|", decode(rec, x, sr, hw))
