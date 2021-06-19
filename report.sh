#!/bin/bash
CUR_DIR=$(cd `dirname ${BASH_SOURCE[0]}`; pwd)
LOG_DIR=/var/log/monitor
python3 $CUR_DIR/report.py > $LOG_DIR/report.txt
if [ -f ${CUR_DIR}/notify.sh ]; then
    ${CUR_DIR}/notify.sh
fi
