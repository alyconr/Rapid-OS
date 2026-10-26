# Feature Lab — In-Memory Booking Availability

Accompanies the canonical tutorial [Feature Engineering Lab](../../docs/tutorials/feature-lab.md).

## Requirements

- `starter/`: Booking system without schedule conflict detection.
- `solution/`: Strict validation that raises `SlotAlreadyBookedError` on attempts to book the same time slot twice.

## Running the tests

```bash
python -m unittest discover examples/feature-lab/starter/tests
python -m unittest discover examples/feature-lab/solution/tests
```
