```
create table ads_pms.ads_pms_skill_test (
      employee_number string comment '员工工号'
    , perf_month date comment '绩效月份'
    , employee_name string comment '员工名称'
    , perf_amt double comment '绩效金额'
    , cargo_volume double comment '货量'
    , attendance_days double comment '出勤天数'
    , job_type string comment '岗位类别'

) duplicate key(employee_number)
comment 'ADS-分析报表-员工绩效-货量 月 表'
partition by range (perf_month) (
start('2025-05-01') end ('2025-12-01')
every (interval 1 month)
)
distributed by hash(employee_number) buckets 3
properties(
'dynamic_partition.enable' = 'true',
'dynamic_partition.time_unit' = 'MONTH',
'dynamic_partition.time_zone' = 'Asia/Shanghai',
'dynamic_partition.end' = '3',
'dynamic_partition.prefix' = 'p',
'storage_type' = 'COLUMN'
)
;
```
