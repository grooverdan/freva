FROM solr:latest

LABEL maintainer="DRKZ-CLINT"
LABEL repository="https://gitlab.dkrz.de/freva/evaluation_system"
ARG NB_USER="freva"
ARG NB_UID="1000"
ARG binder="true"
ENV USER ${NB_USER}
ENV HOME /home/${NB_USER}
ENV SOLR_HOME=${HOME}/.solr \
    MYSQL_HOME=${HOME}/.mysql\
    MYSQL_PORT=3306

## Install Packages
USER root
RUN set -x && \
  apt-get -y update && apt-get -y upgrade &&\
  apt-get -y install acl dirmngr gpg lsof procps netcat wget gosu tini \
             sudo git make vim python3 ffmpeg imagemagick\
             mysql-server libmysqlclient-dev build-essential &&\
  if [ "$binder" = "true" ]; then\
    apt-get -y install python3-cartopy python-cartopy-data python3-xarray zsh nano\
    python3-h5netcdf libnetcdf-dev python3-dask python3-pip;\
  fi &&\
  rm -rf /var/lib/apt/lists/*

## Set all environment variables to run solr and mysql as a ordinary user
ENV NB_USER=${NB_USER} \
    NB_UID=${NB_UID} \
    NB_GROUP=${NB_USER} \
    NB_GID=${NB_UID} \
    SOLR_LOGS_DIR=${SOLR_HOME}/logs/solr \
    LOG4J_PROPS=${SOLR_HOME}/log4j2.xml\
    SOLR_PID_DIR=${SOLR_HOME} \
    MYSQL_LOGS_DIR=${MYSQL_HOME}/logs/mysql \
    MYSQL_DATA_DIR=${MYSQL_HOME}/mysqldata_${MYSQL_PORT} \
    IS_BINDER=$binder \
    PATH="/opt/evaluation_system/bin:/opt/solr/bin:/opt/solr/docker/scripts:$PATH"


COPY . /tmp/evaluation_system

# Setup users/groups and create directory structure
RUN set -x && \
  groupadd -r --gid "$NB_GID" "$NB_GROUP" && \
  adduser --uid "$NB_UID" --gid "$NB_GID" --gecos "Default user" \
  --shell /usr/bin/zsh --disabled-password "$NB_USER" && \
  usermod -aG solr,mysql $NB_USER &&\
  cp /tmp/evaluation_system/src/evaluation_system/tests/mocks/bin/* /usr/local/bin/ && \
  cp /tmp/evaluation_system/.docker/evaluation_system.conf /tmp/evaluation_system/assets &&\
  ln -s /usr/bin/python3 /usr/bin/python &&\
  mkdir -p /opt/evaluation_system/bin &&\
  mkdir -p ${MYSQL_LOGS_DIR} ${SOLR_LOGS_DIR} ${MYSQL_DATA_DIR} ${MYSQL_HOME}/tmpl &&\
  cp /tmp/evaluation_system/.docker/*.sh /opt/evaluation_system/bin/ &&\
  chown -R ${NB_USER}:${NB_GROUP} ${HOME} ${MYSQL_HOME} ${SOLR_HOME} &&\
  chmod +x /opt/evaluation_system/bin/*

# Prepare the mysql server
RUN set -x &&\
  echo "[mysqld]" > /etc/mysql/my.cnf &&\
  echo "user            = ${NB_USER}" >> /etc/mysql/my.cnf &&\
  echo "port            = ${MYSQL_PORT}" >> /etc/mysql/my.cnf &&\
  echo "datadir         = ${MYSQL_DATA_DIR}" >> /etc/mysql/my.cnf &&\
  echo "socket          = ${MYSQL_HOME}/mysql.${MYSQL_PORT}.sock" >> /etc/mysql/my.cnf &&\
  echo "log-error       = ${MYSQL_LOGS_DIR}/mysql-${MYSQL_PORT}-console.err" >> /etc/mysql/my.cnf &&\
  echo "max_connections = 4" >> /etc/mysql/my.cnf &&\
  echo "key_buffer_size = 8M" >> /etc/mysql/my.cnf &&\
  cp /tmp/evaluation_system/.docker/*.sql ${MYSQL_HOME}/tmpl/ &&\
  cp /tmp/evaluation_system/compose/config/mysql/*.sql ${MYSQL_HOME}/tmpl/ &&\
  echo "mysqld --initialize" > /tmp/mysql_init &&\
  echo "nohup mysqld --init-file=${MYSQL_HOME}/tmpl/create_user.sql &" >> /tmp/mysql_init &&\
  echo "mysqladmin --socket=${MYSQL_HOME}/mysql.${MYSQL_PORT}.sock --silent --wait=10 ping || exit 1" >> /tmp/mysql_init &&\
  sudo -E -u ${NB_USER} bash /tmp/mysql_init && rm /tmp/mysql_init &&\
  cat ${MYSQL_LOGS_DIR}/mysql-${MYSQL_PORT}-console.err &&\
  mysql -u freva -pT3st -h 127.0.0.1 -D freva < ${MYSQL_HOME}/tmpl/create_tables.sql


# Prepare the solr server
RUN \
  /opt/solr/docker/scripts/init-var-solr && \
  /opt/solr/docker/scripts/precreate-core latest &&\
  /opt/solr/docker/scripts/precreate-core files &&\
  cp /tmp/evaluation_system/compose/config/solr/managed-schema.xml /var/solr/data/latest/conf/managed-schema.xml &&\
  cp /tmp/evaluation_system/compose/config/solr/managed-schema.xml /var/solr/data/files/conf/managed-schema.xml &&\
  find /var/solr -type d -print0 | xargs -0 chmod 0771 && \
  find /var/solr -type f -print0 | xargs -0 chmod 0661 && \
  cp -r /var/solr ${SOLR_HOME}

RUN \
  if [ "$binder" = "true" ]; then\
    sudo -u $NB_USER git config --global init.defaultBranch main && \
    sudo -u $NB_USER git config --global user.email "freva@my.binder" &&\
    sudo -u $NB_USER git config --global user.name "Freva" &&\
    sudo -u $NB_USER git config --global --add safe.directory /mnt/freva_plugins/dummy &&\
    sudo -u $NB_USER git config --global --add safe.directory /mnt/freva_plugins/animator &&\
    sudo -u $NB_USER cp /tmp/evaluation_system/.docker/zshrc ${HOME}/.zshrc &&\
    cd /tmp/evaluation_system/ &&\
    /usr/bin/python3 -m pip install --no-cache . \
    notebook jupyterhub bash_kernel &&\
    /usr/bin/python3 -m ipykernel install --name freva &&\
    /usr/bin/python3 -m bash_kernel.install &&\
    cp -r /tmp/evaluation_system/.docker/data /mnt/data4freva &&\
    chmod -R 755 /mnt/data4freva &&\
    mkdir -p /etc/jupyter && \
    chmod -R 2777 /usr/freva_output &&\
    cp /tmp/evaluation_system/.docker/*.ipynb $HOME &&\
    cp /tmp/evaluation_system/.docker/jupyter_notebook_config.py /etc/jupyter &&\
    git clone --recursive https://gitlab.dkrz.de/freva/plugins4freva/animator.git /mnt/freva_plugins/animator &&\
    cp -r /tmp/evaluation_system/src/evaluation_system/tests/mocks /mnt/freva_plugins/dummy &&\
    cp /tmp/evaluation_system/.docker/ingest_dummy_data.py /tmp/evaluation_system/compose/solr &&\
    mv /tmp/evaluation_system $HOME/.evaluation_system &&\
    mv $HOME/.evaluation_system/.git /mnt/freva_plugins/dummy ;\
  else \
    rm -r /tmp/evaluation_system && \
    wget https://github.com/allure-framework/allure2/releases/download/2.14.0/allure-2.14.0.tgz -O allure.tgz &&\
    tar xzf allure.tgz -C /opt && mv /opt/allure-2.14.0 /opt/allure && rm allure.tgz ;\
  fi


RUN chown -R ${NB_USER}:${NB_GROUP} ${HOME} ${MYSQL_HOME} ${SOLR_HOME}

EXPOSE 8888
WORKDIR ${HOME}
USER $NB_USER

CMD ["/opt/evaluation_system/bin/loadfreva.sh"]
ENTRYPOINT ["/opt/evaluation_system/bin/docker-entrypoint.sh"]