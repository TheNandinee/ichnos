# IN-RFI-Replay v1 leaderboard

| Region | Method | Day AUC (95% CI) | p (one-sided) | Windows hit (95% CI) | Pos/neg days |
|---|---|---|---|---|---|
| DEL | spoof_jumps | 0.85 (0.72–0.96) | 3.69e-06 | 5/6 (0.44–0.97) | 17/45 |
| DEL | rules_spoof | 0.85 (0.71–0.96) | 1.42e-05 | 5/6 (0.44–0.97) | 17/45 |
| DEL | spoof_altitude | 0.80 (0.66–0.92) | 0.000124 | 5/6 (0.44–0.97) | 17/45 |
| DEL | integrity_jam | 0.79 (0.64–0.92) | 0.000274 | 4/6 (0.30–0.90) | 17/45 |
| DEL | model | 0.73 (0.58–0.86) | 0.00274 | 4/6 (0.30–0.90) | 17/45 |

## Coverage

| Region | Median aircraft/day | Scorable | Reason |
|---|---|---|---|
| ATQ | 194 | False | no dated/period windows |
| BLR | 404 | False | no dated/period windows |
| BOM | 610 | False | no dated/period windows |
| CCU | 440 | False | no dated/period windows |
| DEL | 535 | True |  |
| HYD | 343 | False | no dated/period windows |
| MAA | 148 | False | no dated/period windows |
