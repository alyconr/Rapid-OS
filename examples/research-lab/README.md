# Research Lab — Local Storage Strategy Spike

Accompanies the canonical tutorial [Research & Spike Engineering Lab](../../docs/tutorials/research-lab.md).

## Requirements

- `starter/`: Preliminary spike interface without an implementation.
- `solution/`: Reproducible empirical comparison between flat JSON storage and the embedded SQLite database from the Python standard library.

## Running the tests

```bash
python -m unittest discover examples/research-lab/starter/tests
python -m unittest discover examples/research-lab/solution/tests
```
