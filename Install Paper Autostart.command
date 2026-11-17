#!/bin/zsh
cd "$(dirname "$0")" || exit 1
/usr/bin/python3 integrations/install-service.py
result=$?
if [ "$result" -ne 0 ]; then
  echo '安装未完成，请将上面的错误提示告诉 Codex。'
fi
printf '\n按回车关闭窗口。'
read -r
exit "$result"
