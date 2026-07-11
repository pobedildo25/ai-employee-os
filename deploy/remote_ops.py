#!/usr/bin/env python3
"""Remote SSH operations for production deployment. Secrets via environment only."""

from __future__ import annotations

import argparse
import os
import sys
import textwrap

import paramiko


def connect() -> paramiko.SSHClient:
    host = os.environ.get("DEPLOY_SSH_HOST", "")
    user = os.environ.get("DEPLOY_SSH_USER", "")
    password = os.environ.get("DEPLOY_SSH_PASSWORD", "")
    if not all([host, user, password]):
        print("Set DEPLOY_SSH_HOST, DEPLOY_SSH_USER, DEPLOY_SSH_PASSWORD", file=sys.stderr)
        sys.exit(1)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=30)
    return client


def run(client: paramiko.SSHClient, command: str, *, timeout: int = 300) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return exit_code, out, err


def audit(client: paramiko.SSHClient) -> None:
    commands = [
        "uname -a",
        "docker --version",
        "docker compose version",
        "df -h /",
        "free -h",
        "ss -tlnp 2>/dev/null | head -40 || true",
        "ls -la /home/admin",
        "find /home/admin -maxdepth 4 -name 'ai-employee-os' -type d 2>/dev/null",
        "find /home/admin -maxdepth 5 -name 'docker-compose.prod.yml' 2>/dev/null",
    ]
    for cmd in commands:
        code, out, err = run(client, cmd)
        print(f"\n=== {cmd} (exit {code}) ===")
        if out.strip():
            print(out.strip())
        if err.strip():
            print(err.strip()[:800])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["audit", "run"])
    parser.add_argument("--command", default="")
    args = parser.parse_args()

    client = connect()
    try:
        if args.action == "audit":
            audit(client)
            return 0
        if not args.command:
            print("--command required for run", file=sys.stderr)
            return 1
        code, out, err = run(client, args.command, timeout=900)
        if out:
            print(out, end="" if out.endswith("\n") else "\n")
        if err:
            print(err, file=sys.stderr, end="" if err.endswith("\n") else "\n")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
