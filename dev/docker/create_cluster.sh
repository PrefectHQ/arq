#! /bin/sh

mkdir -p /nodes
touch /nodes/nodemap
if [ -z "${START_PORT}" ]; then
    START_PORT=6379
fi
if [ -z "${END_PORT}" ]; then
    END_PORT=6384
fi
if [ ! -z "$3" ]; then
    START_PORT=$2
    END_PORT=$3
fi
echo "STARTING: ${START_PORT}"
echo "ENDING: ${END_PORT}"

PORT=${START_PORT}
while [ ${PORT} -le ${END_PORT} ]; do
    mkdir -p /nodes/$PORT
    if [ -e /redis.conf ]; then
        cp /redis.conf /nodes/$PORT/redis.conf
    else
        touch /nodes/$PORT/redis.conf
    fi
    cat <<EOF >>/nodes/$PORT/redis.conf
port ${PORT}
cluster-enabled yes
daemonize yes
logfile /redis.log
dir /nodes/$PORT
EOF

    set -x
    /usr/local/bin/redis-server /nodes/$PORT/redis.conf
    sleep 1
    if [ $? -ne 0 ]; then
        echo "Redis failed to start, exiting."
        continue
    fi
    echo 127.0.0.1:$PORT >>/nodes/nodemap
    PORT=$((PORT + 1))
done
if [ -z "${REDIS_PASSWORD}" ]; then
    echo yes | /usr/local/bin/redis-cli --cluster create $(for i in $(seq ${START_PORT} ${END_PORT}); do echo "127.0.0.1:$i"; done) --cluster-replicas 1
else
    echo yes | /usr/local/bin/redis-cli -a ${REDIS_PASSWORD} --cluster create $(for i in $(seq ${START_PORT} ${END_PORT}); do echo "127.0.0.1:$i"; done) --cluster-replicas 1
fi
tail -f /redis.log
