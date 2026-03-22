---

**报告编制说明**：
- 数据来源：ADS 层员工绩效表
- 更新频率：建议每月更新一次
- 责任人：数据分析部 + 人力资源部
- 审批流程：部门负责人 → 财务总监 → 总经理

**联系方式**：如有数据疑问，请联系分析团队。

### 人的基本数据 差值、上月数据
```
select 
    t1.perf_month
, t1.employee_number
, t1.employee_name
, t1.perf_amt
, t1.cargo_volume
, t1.attendance_days
/*上月数据*/
, t2.perf_amt as last_month_perf_amt
, t2.cargo_volume as last_month_cargo_volume
, t2.attendance_days as last_month_attendance_days
/*差值*/
, t1.perf_amt - t2.perf_amt as diff_perf_amt
, t1.cargo_volume - t2.cargo_volume as diff_cargo_volume
, t1.attendance_days - t2.attendance_days as diff_attendance_days
from ads_pms.ads_pms_skill_test t1
left join ads_pms.ads_pms_skill_test t2
on substr(date_sub(t1.perf_month, INTERVAL 1 MONTH),1,7) = t2.perf_month
and t1.employee_number = t2.employee_number
;
```
### 本月的基本数据 差值、上月数据
```
select 
t1.perf_month

, sum(t1.perf_amt) as sum_perf_amt
, sum(t1.cargo_volume) as sum_cargo_volume
, sum(t1.attendance_days) as sum_attendance_days
/*上月数据*/
, sum(t2.perf_amt) as sum_last_month_perf_amt
, sum(t2.cargo_volume) as sum_last_month_cargo_volume
, sum(t2.attendance_days) as sum_last_month_attendance_days
/*差值*/
, sum(t1.perf_amt) - sum(t2.perf_amt)  as sum_diff_perf_amt
, sum(t1.cargo_volume) - sum(t2.cargo_volume)  as sum_diff_cargo_volume
, sum(t1.attendance_days) - sum(t2.attendance_days)  as sum_diff_attendance_days
from ads_pms.ads_pms_skill_test t1
left join ads_pms.ads_pms_skill_test t2
on substr(date_sub(t1.perf_month, INTERVAL 1 MONTH),1,7) = t2.perf_month
and t1.employee_number = t2.employee_number
group by t1.perf_month
;
```