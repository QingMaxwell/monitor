import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import time
import os
import datetime as DT

LOG_PATH="/var/log/monitor"
IMG_PATH="/var/log/monitor"

def diff(data):
    data_1 = np.roll(data,1,axis=0)
    data_1[0]=data[0]
    r = data - data_1
    #return np.maximum(r,0)
    return r

def parse_time(raw):
    dt = [DT.datetime.strptime(t,"%H:%M:%S") for t in raw]
    time=np.uint32(list(np.char.split(raw,':')))
    time_sec=time[:,0]*3600+time[:,1]*60+time[:,2]
    return dt, diff(time_sec)

def parse_cpu(cpu):
    subsample = 20
    cpu_raw=np.int64(cpu[::subsample,0:7])
    cpu_raw_diff=diff(cpu_raw)
    cpu_user=np.float32(cpu_raw_diff[:,0])
    cpu_nice=np.float32(cpu_raw_diff[:,1])
    cpu_system=np.float32(cpu_raw_diff[:,2])
    cpu_idle=np.float32(cpu_raw_diff[:,3])
    cpu_iowait=np.float32(cpu_raw_diff[:,4])
    cpu_irq=np.float32(cpu_raw_diff[:,5])
    cpu_sirq=np.float32(cpu_raw_diff[:,6])
    cpu_total=cpu_user+cpu_nice+cpu_system+cpu_idle+cpu_iowait+cpu_irq+cpu_sirq
    zero_point = np.where(cpu_idle<=0)
    cpu_total[zero_point] = 1
    cpu_idle[zero_point] = 1
    
    cpu_usage_raw=(cpu_total-cpu_idle)/cpu_total*100.0
    cpu_usage_raw[zero_point] = 0
    cpu_usage_raw=cpu_usage_raw.repeat(subsample,axis=0)[0:cpu.shape[0]]

    cpu_usage=np.float32(cpu[:,7])
    cpu_freq=np.float32(cpu[:,8])
    cpu_temp=np.float32(cpu[:,9])
    
    return [{'idx':0, 'name':'CPU Temp (°C)',  'data':cpu_temp,      'avg':'b'},
            {'idx':1, 'name':'CPU Usage1 (%)', 'data':cpu_usage,                'min':0, 'max':110,  'tick':10},
            {'idx':1, 'name':'CPU Usage2 (%)', 'data':cpu_usage_raw, 'avg':'b', 'min':0, 'max':110,  'tick':10},
            {'idx':2, 'name':'CPU Freq (Hz)',  'data':cpu_freq,      'avg':'b'}]

def parse_mem(mem):
    mem_total=np.uint32(mem[0,0])
    mem_cache=np.uint32(mem[:,4])
    mem_avai=np.uint32(mem[:,5])
    mem_used=(mem_total-mem_avai)
    swap_used=np.uint32(mem[:,7])
    swap_total=np.uint32(mem[0,6])
    
    return [{'idx':0, 'name':'MEM Used (MB)',   'data':mem_used,  'min':0, 'max':mem_total+1, 'tick':int(mem_total/1000)*100},
            {'idx':0, 'name':'MEM Cached (MB)', 'data':mem_cache, 'min':0, 'max':mem_total+1, 'tick':int(mem_total/1000)*100},
            {'idx':1, 'name':'SWAP (MB)',       'data':swap_used, 'min':0, 'max':swap_total+1, 'tick':int(swap_total/1000)*100}]

def parse_eth(eth, time_diff):
    if len(eth.shape) == 1:
        data_new = []
        # find all eths
        res = set()
        for d in eth:
            for x in d[0::6]:
                res.add(x)
        res_list = list(res)
        res_list.sort()
        for d in eth:
            record = []
            for r in res_list:
                if r in d:
                    record.append(d[d.index(r):d.index(r)+6])
                else:
                    record.append([r,0,0])
            data_new.append(record)
        data_new = np.array(data_new)
        eth = data_new
    
    eths = eth.reshape(eth.shape[0],-1,3).transpose(1,2,0)
    result = []
    for i,e in enumerate(eths):
        name = e[0][0]
        data_r = np.int64(e[1])
        data_r_diff = diff(data_r)
        data_w = np.int64(e[2])
        data_w_diff = diff(data_w)
        zero_point = np.where(np.logical_or(data_r_diff <= 0, data_w_diff <= 0))
        data_r_diff[zero_point] = 0
        data_w_diff[zero_point] = 0
        time_diff[zero_point] = 1
        time_diff[0] = 1 # avoid divide by 0
        result.append({'idx':i, 'name':name+' R (KB/s)', 'data':data_r_diff/time_diff/1024})
        result.append({'idx':i, 'name':name+' T (KB/s)', 'data':data_w_diff/time_diff/1024})
    return result
    
def parse_disk(disk):
    if len(disk.shape) == 1:
        # [list(
        #     ['sda', '211587.65', '193324.32', '42',
        #      'sdb', '53649.82',  '49159.93',  '43'...]),
        #  list([...]),
        #  ...
        # ]
        disk_new = []
        # find all disks
        res = set()
        for d in disk:
            for x in d:
                if x[0].isalpha() and x != 'S.M.A.R.T.notavailable':
                    res.add(x)
        res_list = list(res)
        res_list.sort()
        for d in disk:
            record = []
            for r in res_list:
                if r in d:
                    tmp = d[d.index(r):d.index(r)+4]
                    if len(tmp) == 4 and tmp[3][0].isalpha():
                        tmp[3] = 'nan'
                    record.append(tmp)
                else:
                    record.append([r,0,0,0])
            disk_new.append(record)
        disk_new = np.array(disk_new)
        
        disk = disk_new
                
    
    disks = disk.reshape(disk.shape[0], -1, 4).transpose(1,2,0)
    
    result = []
    for i,e in enumerate(disks):
        name = e[0][0]
        data_r = np.float32(e[1])
        data_w = np.float32(e[2])
        e[3][e[3]=='S.M.A.R.T.notavailable'] = 'nan'
        temp = np.float32(e[3])
        result.append({'idx':i, 'name':name+' R (KB/s)', 'data':data_r})
        result.append({'idx':i, 'name':name+' W (KB/s)', 'data':data_w})
        result.append({'idx':i, 'name':name+' T (°C)', 'data':temp, 'twinx':1, 'min':0, 'max':70, 'tick':70})
    return result

def parse_partition(data):
    if len(data.shape) == 1:
        data_new = []
        # find all disks
        res = set()
        for d in data:
            for x in d[0::6]:
                res.add(x)
        res_list = list(res)
        res_list.sort()
        for d in data:
            record = []
            for r in res_list:
                if r in d:
                    record.append(d[d.index(r):d.index(r)+6])
                else:
                    record.append([r,0,0,0,0,0])
            data_new.append(record)
        data_new = np.array(data_new)
        data = data_new
    
    disks = data.reshape(data.shape[0], -1, 6).transpose(1,2,0)
    result = []
    for i,e in enumerate(disks):
        name = e[0][0].replace("/dev/","")
        data_percent = []
        used = []
        size = []
        for x in e[3]:
            y = x.replace("G","")
            used.append(int(y))
        for x in e[2]:
            y = x.replace("G","")
            size.append(int(y)/1024)
        maxsize = np.max(size)
        for x in e[5]:
            y = x.replace("%","")
            data_percent.append(int(y))
            
        result.append({'idx':i, 'name':name+" used (GB)", 'data':used})
        result.append({'idx':i, 'name':name+" use (%)", 'data':data_percent, 'twinx':1, 'min':0, 'max':100, 'tick':100})
        
    return result

def add_data(plots_cfg, datas, max_cols, color_list):
    last_idx = 0
    color_id = 0
    datas.sort(key=lambda item : item['idx'])
    if len(plots_cfg) != 0:
        last = plots_cfg[-1]
        last_col = last['col']+1
        last_row = last['row']
    else:
        last_col = 0
        last_row = 0
    for i,d in enumerate(datas):
        idx = d['idx']

        # change position
        new_col = (last_col + idx) % max_cols
        new_row = last_row + int((last_col + idx) / max_cols)
        
        d['col'] = new_col
        d['row'] = new_row
        
        # color
        if i > 0:
            color_id = color_id + 1 if last_idx == idx else 0

        last_idx = idx
        d['color'] = '#000000' if color_id >= len(color_list) else color_list[color_id]
        plots_cfg.append(d)
    
def get_rectime(default_date, time):
    
    try:
        time = time.strip(b'\x00'.decode())
        time_array=np.uint32(time.split(':'))
        return DT.datetime(default_date.year, default_date.month, default_date.day, time_array[0], time_array[1], time_array[2])
    except:
        return np.NaN

    
def get_logdata(start_time, end_time):
    delta = DT.timedelta(days=1)
    time = start_time
    all_data = []
    all_time = []
    while time < end_time:
        year = time.year
        month = time.month
        day = time.day
        log_file = "{}/{}/{:0>2d}{:0>2d}.txt".format(LOG_PATH,year,month,day)
        time1 = time
        time2 = DT.datetime(time.year, time.month, time.day, 23, 59, 59, 999999)
        if time2 > end_time:
            time2 = end_time
        try:
            raw_data = np.loadtxt(log_file,dtype=str,delimiter=',')
        except:
            print('failed to load file', log_file)
            time = time + delta
            time = DT.datetime(time.year, time.month, time.day)
            continue
        dt = [get_rectime(time, t) for t in raw_data[:,0]]
        dt = np.array(dt)
        sub_data = raw_data[np.where(dt>time1)]
        dt = dt[np.where(dt>time1)]
        all_data.append(sub_data)
        all_time.append(dt.reshape(-1,1))
        
        time = time + delta
        time = DT.datetime(time.year, time.month, time.day)
    all_data = np.vstack(all_data)
    all_time = np.vstack(all_time)
    all_time = all_time.flatten()
    
    if all_data.shape[0] == 0:
        raise IOError
    
    # time diff
    time_sec = [t.timestamp() for t in all_time]
    time_diff = diff(time_sec)
    
    # fill empty data
    MAX_DIFF = 50
    INSERT_DELTA = 10
    loss_data_points = np.where(time_diff > MAX_DIFF)
    offset = 0
    for point in loss_data_points[0]:
        if point > 1:
            start_time = all_time[point+offset-1]
            end_time = all_time[point+offset]
            delta_time = end_time - start_time
            #insert_num = int(delta_time.total_seconds() / INSERT_DELTA)
            insert_1_time = start_time + DT.timedelta(seconds=INSERT_DELTA)
            insert_2_time = end_time - DT.timedelta(seconds=INSERT_DELTA)
            #     |<--------------------------- loss data ---------------------------->|
            # start_time ---- insert_1 ---------------------------- insert_2 ---- end_time
            #     |<---- 10s ---->|                                    |<---- 10s ---->|
            
            dummy_cpu = str(np.zeros(10,dtype=np.int32))[1:-1]
            dummy_mem = str(np.zeros(9,dtype=np.int32))[1:-1]
            insert_datas = np.array([
                [insert_1_time.strftime("%H:%M:%S"), dummy_cpu, dummy_mem, '', '', ''],
                [insert_2_time.strftime("%H:%M:%S"), dummy_cpu, dummy_mem, '', '', '']], dtype=str)
            insert_times = np.array([insert_1_time, insert_2_time])
            insert_diffs = np.array([INSERT_DELTA, INSERT_DELTA])
            all_data = np.insert(all_data, point+offset, insert_datas, 0)
            all_time = np.insert(all_time, point+offset, insert_times, 0)
            time_diff = np.insert(time_diff, point+offset, insert_diffs, 0)
            
            offset = offset + 2
    return all_time, all_data, time_diff


def draw(dt, plots_cfg, file_name, max_cols):
    fig, axs = plt.subplots(nrows=plots_cfg[-1]['row']+1, ncols=max_cols, figsize=(10.8, 24))
    
    for i,cfg in enumerate(plots_cfg):
        ax = axs[cfg['row'],cfg['col']] if max_cols > 1 and plots_cfg[-1]['row'] > 0 else axs[cfg['row']]
        
        #ax.set_title(cfg['name'])
        
        if 'twinx' in cfg:
            ax2 = ax.twinx()
            ax = ax2
        
        if 'min' in cfg and 'max' in cfg:
            ax.set_ylim(cfg['min'],cfg['max'])
            if 'tick' in cfg:
                ax.set_yticks(range(cfg['min'],cfg['max']+1,cfg['tick']))
        
        ax.xaxis.set_minor_locator(mdates.HourLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H'))
        ax.xaxis.set_minor_locator(mdates.HourLocator(interval=1))

        ax.grid(True)
        ax.plot(dt, cfg['data'], c=cfg['color'], label=cfg['name'])
        
        # show max value
        max_pos = np.nanargmax(cfg['data'])
        max_val = cfg['data'][max_pos]
        max_time = dt[max_pos]
        
        avg_val = np.nanmean(cfg['data'])
        msg_full = '{:<16s} max: {:>8.2f} @ {} avg: {:>8.2f}'.format(cfg['name'], max_val, str(max_time), avg_val)
        print(msg_full)
        msg = str(max_val)
        msg_x = dt[max_pos]
        msg_y = max_val
        
        # show avg line
        if 'avg' in cfg:
            ax.axhline(y=avg_val, color=cfg['avg'], linestyle=':')
        
        #ax.plot(msg_x,msg_y,'ks')
        ax.annotate(msg, (msg_x,msg_y), xytext=(msg_x,msg_y), fontsize=10,
            horizontalalignment='left', verticalalignment='bottom')
        ax.legend()
        
    # delete empty sub plots
    if (max_cols > 1):
        last = plots_cfg[-1]
        last_col = last['col']+1
        last_row = last['row']
        for c in range(last_col, max_cols):
            fig.delaxes(axs[last_row, c])
    
    #plt.show()
    plt.savefig(file_name)
    
    
def report(file_name):
    # defins
    max_cols = 3
    color_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    now = DT.datetime.now()
    delta = DT.timedelta(days=2)
    day_before = now - delta
    print('Sys report from {} to {}'.format(str(day_before), str(now)))
    try:
        dt, logdata, time_diff = get_logdata(day_before, now)
    except:
        print("no data loaded")
        return
    
    # parse data
    #dt, time_diff = parse_time(logdata[:,0])
    cpu_datas  = parse_cpu(np.array(list(np.char.split(logdata[:,1]))))
    mem_datas  = parse_mem(np.array(list(np.char.split(logdata[:,2]))))
    eths_datas = parse_eth(np.array(list(np.char.split(logdata[:,3]))), time_diff)
    disk_datas = parse_disk(np.array(list(np.char.split(logdata[:,4]))))
    partition_datas = parse_partition(np.array(list(np.char.split(logdata[:,5]))))
    
    # add to plot
    basic_plots = []
    add_data(basic_plots, cpu_datas,  max_cols, color_list)
    add_data(basic_plots, mem_datas,  max_cols, color_list)
    add_data(basic_plots, eths_datas, max_cols, color_list)
    
    add_data(basic_plots, disk_datas, max_cols, color_list)
    add_data(basic_plots, partition_datas, max_cols, color_list)
    
    # plot
    draw(dt, basic_plots, file_name, max_cols)
    #draw(dt, disk_plots,  disk_info, max_cols)
    

report(IMG_PATH+"/report.png")
