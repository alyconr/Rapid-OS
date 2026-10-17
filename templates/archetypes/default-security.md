# 🛡️ SECURITY STANDARD (MINIMAL)

Edit this file to match your project. `rapid start hardening` requires it.

1. **Secrets:** never commit `.env` files, keys or tokens; use a secret manager.
2. **Input:** validate and bound every external input before using it (types, lengths, allowed values).
3. **Injection:** use parameterized queries and safe APIs; never build SQL, shell commands or paths by string concatenation.
4. **Auth:** check authentication and authorization on every private operation.
5. **Data:** do not log personal data or credentials; return errors that do not leak internals.
6. **Dependencies:** pin and review new dependencies before adding them.
