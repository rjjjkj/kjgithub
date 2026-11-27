# AGENTS.md - kjgithub Fleet Operations

## Role & Boundaries
- 実行・実機検証は「みちのく」が担当し、設計案の破壊的変更は `k2` 承認後に実行する。
- 推測で設定値・IP・パスを補完しない。不明な実機状態は読み取り専用コマンドで確認する。

## Verification Commands
- `k2-server` サービス確認: `systemctl status a2a-server k2-mcp dsp-api --no-pager`
- Tailscale 確認: `tailscale status`

## Forbidden Operations (Require `k2` Approval)
- `rm`、`ufw` 変更、`camilladsp` 再起動、Tailscale / AdGuard Home の設定変更
- みちのく／対話エージェントによるアドホックな `systemctl restart` / `systemctl stop`
  - **例外**: 承認済み `autofix-net` ポリシーに基づく `fastapi` / `dsp-api` / `ollama` の定常自動復旧（最大2回・30分クールダウン）は許可対象
