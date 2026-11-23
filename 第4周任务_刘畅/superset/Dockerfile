# Superset 定制镜像：官方镜像 + Hive/MySQL 连接驱动
# 手册技术难点：Superset 连 Hive 需额外 JDBC/Python 驱动
FROM apache/superset:4.1.1

USER root

# 安装 Hive 连接驱动（pyhive + thrift）与 MySQL 驱动
RUN pip install --no-cache-dir \
      pyhive==0.7.0 \
      thrift==0.16.0 \
      thrift-sasl==0.4.3 \
      pymysql==1.1.0 \
      sqlalchemy-hive==1.1.6

USER superset
