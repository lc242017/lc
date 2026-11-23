#!/bin/bash
# ============================================
# Superset 初始化脚本（手册步骤1，已修正命令顺序）
# 原手册错误：先 create-admin 再 db upgrade（空库会失败）
# 正确顺序：db upgrade -> create-admin -> init
# ============================================
set -e

echo ">>> 1/3 初始化数据库元数据"
superset db upgrade

echo ">>> 2/3 创建管理员账号"
superset fab create-admin \
  --username "${SUPERSET_ADMIN_USER:-admin}" \
  --firstname Admin \
  --lastname User \
  --email "${SUPERSET_ADMIN_EMAIL:-admin@example.com}" \
  --password "${SUPERSET_ADMIN_PASSWORD:-admin}"

echo ">>> 3/3 初始化权限与角色"
superset init

echo ">>> Superset 初始化完成，访问 http://localhost:8088"
