# 🛡️ SECURITY PROTOCOLS (NON-NEGOTIABLE)
1. **Secrets:** NEVER commit .env files. Use Secret Managers.
2. **Injection:** Use ORM parameterization. NEVER concatenate SQL.
3. **Auth:** Validate JWT on every private endpoint.
4. **PII:** Do not log emails or phones in plain text.