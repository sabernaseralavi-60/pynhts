"""Conditional VAE over 288 five-minute activity tokens (pilot, CPU) and the privacy metric (DCR)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F

from diary import N_SLOTS
from models import N_STATES

COV_DIMS = {"age": 6, "worker": 2, "weekend": 2, "veh": 3}


def cov_onehot(cov: pd.DataFrame) -> torch.Tensor:
    parts = [F.one_hot(torch.as_tensor(cov[c].to_numpy(dtype=np.int64)), n).float()
             for c, n in COV_DIMS.items()]
    return torch.cat(parts, dim=1)


class _Net(nn.Module):
    def __init__(self, hidden: int, latent: int) -> None:
        super().__init__()
        c = sum(COV_DIMS.values())
        self.enc = nn.Sequential(nn.Linear(N_SLOTS * N_STATES + c, hidden), nn.ReLU(),
                                 nn.Linear(hidden, hidden), nn.ReLU())
        self.mu, self.logvar = nn.Linear(hidden, latent), nn.Linear(hidden, latent)
        self.dec = nn.Sequential(nn.Linear(latent + c, hidden), nn.ReLU(),
                                 nn.Linear(hidden, hidden), nn.ReLU(),
                                 nn.Linear(hidden, N_SLOTS * N_STATES))
        self.latent = latent

    def forward(self, x: torch.Tensor, c: torch.Tensor):
        h = self.enc(torch.cat([x.flatten(1), c], dim=1))
        mu, lv = self.mu(h), self.logvar(h)
        z = mu + torch.randn_like(mu) * torch.exp(0.5 * lv)
        return self.dec(torch.cat([z, c], dim=1)).view(-1, N_SLOTS, N_STATES), mu, lv


class ConditionalVAE:
    """Survey-weighted conditional VAE; one categorical draw per slot given the latent code."""

    name = "cvae"
    decode = "sample"  # "sample": independent categorical draw per slot; "mode": argmax per slot

    def __init__(self, hidden: int = 512, latent: int = 32, epochs: int = 12, batch: int = 512,
                 lr: float = 1e-3, beta: float = 1.0, seed: int = 0) -> None:
        self.h, self.k, self.epochs, self.batch, self.lr, self.beta = hidden, latent, epochs, batch, lr, beta
        self.seed = seed

    def fit(self, diary: np.ndarray, cov: pd.DataFrame, w: np.ndarray) -> ConditionalVAE:
        torch.manual_seed(self.seed)
        self.net = _Net(self.h, self.k)
        opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        x = torch.as_tensor(diary, dtype=torch.long)
        c = cov_onehot(cov)
        wt = torch.as_tensor(w / w.mean(), dtype=torch.float32)
        n = len(x)
        for ep in range(self.epochs):
            perm = torch.randperm(n)
            tot = 0.0
            for i in range(0, n, self.batch):
                idx = perm[i: i + self.batch]
                xb, cb, wb = x[idx], c[idx], wt[idx]
                logits, mu, lv = self.net(F.one_hot(xb, N_STATES).float(), cb)
                rec = F.cross_entropy(logits.reshape(-1, N_STATES), xb.reshape(-1),
                                      reduction="none").view(len(idx), -1).sum(1)
                kl = -0.5 * (1 + lv - mu**2 - lv.exp()).sum(1)
                loss = ((rec + self.beta * kl) * wb).mean()
                opt.zero_grad()
                loss.backward()
                opt.step()
                tot += loss.item() * len(idx)
            print(f"  cvae epoch {ep + 1}/{self.epochs} loss {tot / n:.2f}", flush=True)
        return self

    @torch.no_grad()
    def generate(self, cov: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
        torch.manual_seed(int(rng.integers(2**31)))
        c = cov_onehot(cov)
        out = []
        for i in range(0, len(c), 8192):
            cb = c[i: i + 8192]
            z = torch.randn(len(cb), self.net.latent)
            logits = self.net.dec(torch.cat([z, cb], dim=1)).view(-1, N_SLOTS, N_STATES)
            tok = (logits.argmax(-1) if self.decode == "mode"
                   else torch.distributions.Categorical(logits=logits).sample())
            out.append(tok.to(torch.uint8))
        return torch.cat(out).numpy()


@torch.no_grad()
def dcr(query: np.ndarray, reference: np.ndarray, chunk: int = 20000) -> np.ndarray:
    """Distance to closest record: smallest share of the 288 slots that differ from any reference."""
    q = F.one_hot(torch.as_tensor(query, dtype=torch.long), N_STATES).float().flatten(1)
    best = torch.zeros(len(q))
    for i in range(0, len(reference), chunk):
        r = F.one_hot(torch.as_tensor(reference[i: i + chunk], dtype=torch.long), N_STATES)
        best = torch.maximum(best, (q @ r.float().flatten(1).T).max(dim=1).values)
    return (1.0 - best / N_SLOTS).numpy()
