-- ============================================
-- 数据质量预评估（五维度：完整性/唯一性/有效性/一致性/准确性）
-- ============================================

-- 1. 完整性：关键字段空值统计
select 'user' tab, 'age' col, sum(case when age is null then 1 else 0 end) null_cnt, count(*) total from ydsh_ods.ods_user
union all select 'user', 'email', sum(case when email is null or email='' then 1 else 0 end), count(*) from ydsh_ods.ods_user
union all select 'user', 'phone', sum(case when phone is null or phone='' then 1 else 0 end), count(*) from ydsh_ods.ods_user
union all select 'product', 'launch_date', sum(case when launch_date is null or launch_date='' then 1 else 0 end), count(*) from ydsh_ods.ods_product
union all select 'order', 'pay_amount', sum(case when pay_amount is null or pay_amount='' then 1 else 0 end), count(*) from ydsh_ods.ods_order
union all select 'order_item', 'discount', sum(case when discount is null then 1 else 0 end), count(*) from ydsh_ods.ods_order_item
union all select 'user_behavior', 'behavior_time', sum(case when behavior_time is null or behavior_time='' then 1 else 0 end), count(*) from ydsh_ods.ods_user_behavior
union all select 'store', 'open_date', sum(case when open_date is null or open_date='' then 1 else 0 end), count(*) from ydsh_ods.ods_store;

-- 2. 唯一性：主键重复统计
select 'user' tab, count(*) dup_rows from (select user_id from ydsh_ods.ods_user group by user_id having count(*)>1) t
union all select 'product', count(*) from (select product_id from ydsh_ods.ods_product group by product_id having count(*)>1) t
union all select 'store', count(*) from (select store_id from ydsh_ods.ods_store group by store_id having count(*)>1) t
union all select 'order', count(*) from (select order_id from ydsh_ods.ods_order group by order_id having count(*)>1) t
union all select 'order_item', count(*) from (select item_id from ydsh_ods.ods_order_item group by item_id having count(*)>1) t
union all select 'user_behavior', count(*) from (select behavior_id from ydsh_ods.ods_user_behavior group by behavior_id having count(*)>1) t;

-- 3. 有效性：枚举字段取值分布
select 'user.gender' f, gender v, count(*) c from ydsh_ods.ods_user group by gender
union all select 'user.member_level', member_level, count(*) from ydsh_ods.ods_user group by member_level
union all select 'order.pay_type', pay_type, count(*) from ydsh_ods.ods_order group by pay_type
union all select 'order.order_status', order_status, count(*) from ydsh_ods.ods_order group by order_status
union all select 'order.channel', channel, count(*) from ydsh_ods.ods_order group by channel
union all select 'behavior.type', behavior_type, count(*) from ydsh_ods.ods_user_behavior group by behavior_type
union all select 'product.status', status, count(*) from ydsh_ods.ods_product group by status;

-- 4. 准确性：年龄异常值
select count(*) bad_age from ydsh_ods.ods_user where age is null or age<1 or age>120;

-- 5. 一致性：外键引用
select 'order.user_id 缺失' chk, count(*) c from ydsh_ods.ods_order o left join ydsh_ods.ods_user u on o.user_id=u.user_id where u.user_id is null
union all select 'order.store_id 缺失', count(*) from ydsh_ods.ods_order o left join ydsh_ods.ods_store s on o.store_id=s.store_id where s.store_id is null
union all select 'order_item.order_id 缺失', count(*) from ydsh_ods.ods_order_item oi left join ydsh_ods.ods_order o on oi.order_id=o.order_id where o.order_id is null;
