# 华为云 KooLabs 实验操作手册（加速版）

## 0. 开工前

- 确认今日免费名额和实验点足够。
- 在 `desktop-operator` 的专用 Edge profile 里登录一次华为云，后续复用 Cookie。
- 记录实验总时长；RDS 主备通常需要 7-15 分钟，不要把它放在最后。

## 1. 资源顺序

1. **先下单 RDS**（MySQL 5.7、主备、本地SSD、2C4G、40GB）。
2. RDS 创建期间，创建共享带宽、安全组、VPC。
3. 创建 ECS（s6.small.1、CentOS 7.4、40GB 高IO、绑定共享带宽）。
4. ECS 起来后立刻 SSH 装 LAMP、下载 WordPress，不等待 RDS。
5. RDS 可用后建库、配置 WordPress。

## 2. 安全组的关键坑

平台报告检查“添加安全组规则”时，认的是**默认安全组**，不是新建的 `sg-WP`。

- 自定义安全组 `sg-WP`：入方向 `0.0.0.0/0`、全部协议、优先级 1。
- 默认安全组 `default`：同样添加一条 `0.0.0.0/0`、全部协议、优先级 1。
- 两条都加，2.3 检查点才会变绿。

## 3. 检查点探针

每完成一大步，切到“实验报告”，用响应捕获直接读 6 个检查点：

```powershell
cd desktop-operator
.\op.ps1 browser.capture_response `
  "url=<实验操作页URL>" `
  "click_selector=text=实验报告" `
  "match=gen-experiment-report" `
  "timeout=20000"
```

返回 JSON 里的 `result.step_info` 就是：

- 1.2 购买共享带宽
- 2.3 添加安全组规则
- 3.2 创建虚拟私有云
- 4.3 设置用户名和密码确认购买ECS
- 6.5 创建WordPress数据库
- 7.1 进入数据库配置页面

发现“未完成”就先修，不要等到最后。

## 4. 7.1 的特殊情况

7.1 是“进入数据库配置页面”，不是“网站已安装”。如果先完成了 WordPress 安装，该检查点可能一直不绿。

如果必须 100%：

1. 先让 `http://EIP/wordpress/` 能跳到 `setup-config.php`，确认报告 7.1 变绿。
2. 再做数据库配置和安装。
3. 安装完成后再看一次报告。

如果更看重可用站点，可以接受 7.1 未绿，但要在最终说明里写清楚 7.2/7.3 已实际验证。

## 5. ECS 侧命令

```bash
yum install -y httpd php php-fpm php-mysql mysql unzip
grep -q '^ServerName localhost:80' /etc/httpd/conf/httpd.conf || echo 'ServerName localhost:80' >> /etc/httpd/conf/httpd.conf
curl -L -o /root/wordpress.zip https://edu-res.hc-cdn.cn/sharedata/hdinnovation/sandbox/lab2024/30min-website/wordpress-4.9.1-zh_CN.zip
unzip -o -d /var/www/html /root/wordpress.zip
chmod -R 777 /var/www/html
systemctl start httpd php-fpm
systemctl enable httpd php-fpm
```

数据库：

```bash
mysql -h <RDS内网IP> -uroot -p -e "CREATE DATABASE IF NOT EXISTS wordpress;"
```

## 6. 凭据处理

- 不要把密码写进命令行参数或聊天文本。
- 用 `Read-Host -AsSecureString` 或本地 ACL 限制的 secret 文件。
- 自动化脚本从环境变量/secret 读取，日志只记录“已设置/未设置”。
