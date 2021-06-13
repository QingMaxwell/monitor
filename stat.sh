#!/bin/bash

disk_temp() {
    disk=$1
    if [[ ${disk} == nvme* ]]; then
        sudo nvme smart-log /dev/${disk} | grep '^temperature' | awk '{print $3}'
    elif [[ ${disk} == sd* ]]; then
        sudo hddtemp /dev/${disk} | awk -F: '{print $3}' | sed 's/[ °C]//g'
    fi
}

stat() {
    CPU_USAGE=`top -b -n 1 | grep Cpu | awk '{print 100-$8}'`
    CPU_FREQ=`lscpu | grep 'CPU MHz' | awk '{print $3}'`
    CPU_THERMAL=`sensors | grep 'Package id 0'`
    CPU_THERMAL=${CPU_THERMAL#*+}
    CPU_THERMAL=${CPU_THERMAL%%°C*}
    CPU_STAT=`cat /proc/stat | grep -w cpu | awk '{print $2, $3, $4, $5, $6, $7, $8}'`
    CPU="$CPU_STAT $CPU_USAGE $CPU_FREQ $CPU_THERMAL"
    MEM=`free -m | sed 's/[^0-9 ]*//g' | xargs`
    NET=`cat /proc/net/dev | grep -v 'lo' | awk '{if(NR>2){print $1,$2,$10}}' | sed 's/://g'`
    DISKS=`iostat -d | grep -v 'loop' | awk '{if(NR>3){print $1}}' | xargs`
    DISK_INFO=`for d in ${DISKS}; do iostat -d /dev/$d | awk '{if(NR>3){print $1,$3,$4}}'; disk_temp $d; done`
    PARTITION=`for d in ${DISKS}; do df -BG | grep $d; done | awk '{print $1,$6,$2,$3,$4,$5}' | xargs`

    STAT="$CPU, $MEM, $NET, $DISK_INFO, $PARTITION"
}

stat
echo $STAT
