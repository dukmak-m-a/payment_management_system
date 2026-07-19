"""Generate a password hash for a new Accounts row.

Usage:  python generate_hash.py
Prompts for the password (hidden — getpass never echoes it and it never
lands in shell history), prints the hash. Paste the hash into the
"PasswordHash" column when creating the account in the Supabase dashboard.

The plaintext password is never stored anywhere — only this one-way hash.
Login later verifies with check_password_hash(), which re-hashes the
attempt with the same salt and compares in constant time (never compare
hashes with ==).
"""
from getpass import getpass

from werkzeug.security import generate_password_hash

password = getpass("Password for the new account: ")
confirm = getpass("Confirm password: ")

if password != confirm:
    raise SystemExit("Passwords do not match — nothing generated.")
if len(password) < 8:
    raise SystemExit("Refusing: use at least 8 characters.")

# Output format: method$salt$hash — the salt is random per call, so the
# same password produces a different hash every time. That's correct:
# it defeats rainbow-table lookups and hides shared passwords.
print("\n" + generate_password_hash(password))
