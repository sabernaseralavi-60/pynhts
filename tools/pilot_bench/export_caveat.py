"""Write split-`sp` NHTS 2017 train schedules + attributes in caveat's CSV format and a run config."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from schedule import diary_to_schedule

sp = int(sys.argv[1]) if len(sys.argv) > 1 else 0
epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 20
out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(common.ROOT / "local_data" / "caveat_run")
out.mkdir(parents=True, exist_ok=True)
b = common.load(); tr, te = b.split(sp)
sched = diary_to_schedule(b.diary)
n = sched.groupby("pid").size()
keep = n.index[n <= 16]
def attrs(mask):
    c = b.cov[mask]
    return pd.DataFrame({"pid": np.flatnonzero(mask), "age": c["age"].astype(str).to_numpy(),
                         "worker": c["worker"].astype(str).to_numpy(),
                         "veh": c["veh"].astype(str).to_numpy(), "weekend": c["weekend"].astype(str).to_numpy()})
tr_pids = np.intersect1d(np.flatnonzero(tr), keep)
sched[sched.pid.isin(tr_pids)].to_csv(out / "train_schedules.csv", index=False)
attrs(np.isin(np.arange(len(tr)), tr_pids)).to_csv(out / "train_attributes.csv", index=False)
attrs(te).to_csv(out / "test_attributes.csv", index=False)
cfg = f"""logging_params:
  log_dir: "{(out / 'logs').as_posix()}"
  name: "nhts_split{sp}"
schedules_path: "{(out / 'train_schedules.csv').as_posix()}"
attributes_path: "{(out / 'train_attributes.csv').as_posix()}"
synthetic_attributes_path: "{(out / 'test_attributes.csv').as_posix()}"
labels_encoder:
  name: "tokens"
  labels:
    age: nominal
    worker: nominal
    veh: nominal
    weekend: nominal
encoder_params:
  name: "continuous"
  max_length: 16
  norm_duration: 1440
  jitter: 0.1
model_params:
  name: "CVAEContLSTM"
  hidden_n: 2
  hidden_size: 128
  latent_dim: 6
  dropout: 0.1
  teacher_forcing_ratio: 0.5
loader_params:
  train_batch_size: 512
  val_batch_size: 512
  num_workers: 2
experiment_params:
  LR: 0.002
  weight_decay: 0.0
  scheduler_gamma: 0.975
  kld_weight: 0.005
trainer_params:
  patience: 8
  max_epochs: {epochs}
seed: 1234
"""
(out / "run.yaml").write_text(cfg)
print("train persons", len(tr_pids), "test persons", te.sum(), "->", out)
