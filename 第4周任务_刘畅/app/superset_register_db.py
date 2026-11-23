# -*- coding: utf-8 -*-
"""
通过 Superset CLI（app context）注册 MySQL(ydsh_ads) 数据源（手册步骤1）。
说明：Superset 4.x 的 REST API 在添加数据库时会强制连接检查，容易因容器内
DNS / IPv6 解析问题误报 "Connection failed"；用 CLI 直接写入数据模型更可靠。
在 Superset 容器内运行：python /app/superset_register_db.py
"""
from sqlalchemy import create_engine, text
from superset.app import create_app

DB_NAME = "ydsh_ads"
# 用 Docker 网桥 IPv4 网关访问宿主机 MySQL（host.docker.internal 在部分环境解析为 IPv6 导致失败）
URI = "mysql+pymysql://root:root@172.17.0.1:3307/ydsh_ads?charset=utf8mb4"


def main():
    app = create_app()
    with app.app_context():
        from superset import db
        from superset.models.core import Database

        existing = db.session.query(Database).filter_by(database_name=DB_NAME).first()
        if existing:
            print(f"[OK] 数据源已存在 id={existing.id}")
            d = existing
        else:
            d = Database(database_name=DB_NAME, sqlalchemy_uri=URI)
            db.session.add(d)
            db.session.commit()
            print(f"[OK] 数据源已创建 id={d.id}")

        # 验证连接
        with d.get_sqla_engine() as eng:
            with eng.connect() as c:
                cnt = c.execute(text("select count(*) from ads_kpi")).scalar()
        print(f"[OK] 连接验证成功：ads_kpi 共 {cnt} 行")


if __name__ == "__main__":
    main()
