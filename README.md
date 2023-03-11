<p align="center"><strong>Auto Install & Optimize LEMP Stack on Ubuntu (18.04, 20.04)</strong></p>
<p align="center"><strong>##############################################</strong></p>


This is a shell script used to install LEMP Stack (Nginx - MariaDB - PHP-FPM) on Ubuntu (18.04, 20.04), Debian 10.

<b>Please do not copy or distribute this for commercial purposes, donations. Thank you.</b>

## 1. Script Details:

### 1.1. Installation

- Continuously updated, providing a menu to make it easy to operate and automatically install.
- Install software with the latest version from the official website.
- Mariadb: 10.5.
- Nginx Stable version.
- Allow choosing PHP version: 5.6, 7.0, 7.1, 7.2, 7.3, 7.4, 8.0.
- phpMyAdmin 4.9.x if default PHP version is 5.6, phpMyAdmin 5.0.x if default PHP version is 7.x.
- Configure Nginx FastCGI cache.
- Configure Nginx Pagespeed.
- Install PHPMemcachedAdmin, phpRedisAdmin, Opcache Dashboard.
- Install memcached, redis cache. (not enabled by default).
- Install Fail2ban.
- Integrate Let's Encrypt SSL.
- Integrate CloudFlare DNS API to speed up SSL verification.
- Provide upgrade menu for Nginx, MariaDB, PHP, Redis, Memcached, phpMyAdmin.
- Install WP-CLI, Composer, supervisor, Rclone.
- Install ClamAV, ImunifyAV.
- DO NOT COLLECT ANY INFORMATION ON YOUR VPS.

### 1.2. Optimization

- Optimize MySQL, Nginx, PHP, Opcache, Memcached, Redis configuration according to VPS specifications.
- Configure Brotli Compress.
- Configure URL rewrite with some popular source code: WordPress, Laravel, Opencart, Magento, Drupal...
- Allow running two PHP versions in parallel.
- Easy FTP management in case you hire a coder and only want them to have access to a specific directory.
- Allow choosing Redis Cache or Memcached to speed up the website.
- Allow automatic renewal configuration for Let's Encrypt.
- Support SSL configuration menu for paid SSL.
- Menu to view error log for Nginx, Mysql, PHP and view by specific domain name.
- Automatic cronjob to update the latest Cloudflare IP range for Nginx and CSF Firewall.
- And More...

### 1.3. Security

- Enhance security configuration from the web server layer.
- Configure websites to run with different users to limit the spread of malware between websites.
- Disable dangerous functions, enable open_basedir and some other configs to enhance security.
- Auto block bruteforce SSH, SFTP, Admin Tool ... with Fail2ban.
- Block running shell in WordPress uploads directory. Block access to sensitive directories and files on WordPress.
- Prevent Bruteforce wp-admin.
- Block, Unblock IP easily with Firewall management menu.
- Disable User API - /wp-json/wp/v2/users - on WordPress to avoid leaking user information.
- Change SSH port to avoid SSH scanning.
- Allow changing Admin port.
- Allow changing SSH/SFTP port.
- Automatically generate strong passwords.
- Scan Malware with Clamav, ImunifyAV.
- And More ...

### 1.4. WordPress Management

- Check the WordPress version in use.
- Update WordPress.
- Update plugins.
- Optimize Database.
- Repair Database.
- Backup data (Local/GG Drive).
- Restore data (Local/GG Drive).
- Change domain name.
- Change admin password (wp-admin).
- Install WordPress automatically.
- Turn on/off Yoast Seo config.
- Turn on/off Rank Math Seo config.
- Configure Nginx with some popular cache plugins: WP-Rocket, w3 total cache, wp supercache, Cache Enabler, Swift Performance, Fast cache.
- Add cache key to avoid duplicate content between sites when using memcached or redis.
- Turn on/off Debug.
- Turn on/off maintenance mode.
- Turn on/off disable xmlrpc (By default, xmlrpc will be disabled to prevent DDOS exploitation).
- Deactivate all plugins.
- Random database prefix when using automatic installation feature.
- And more ...

### 1.5. Backup/Restore data
- Backup and restore data from Google Drive with Rclone.
- Backup, restore locally.
- Set the number of backup copies to store.
- Manage backups.
- Allow connecting multiple Google Drive accounts.

## 2. Requirements

- VPS with at least 512MB ram and no services installed.
- Ubuntu 18.04, 20.04, Debian 10.

## 3. Installation

```sh
curl -sO https://f97.github.io/hostvn/install && chmod +x install && ./install
```

## 4. Features to be developed

- Features according to user requests

## 5. How to use

- Please visit: https://help.hostvn.vn/

## 6. Software download sources

- Nginx: http://nginx.org/en/download.html
- MariaDB: https://downloads.mariadb.org/
- PHP: https://www.php.net/
- phpMyAdmin: https://www.phpmyadmin.net/
- PHPMemcachedAdmin: https://github.com/elijaa/phpmemcachedadmin
- phpRedisAdmin: https://github.com/erikdubbelboer/phpRedisAdmin
- Rclone: https://rclone.org/
- WP-CLI: https://wp-cli.org/
- Composer: https://getcomposer.org/
- ClamAV: https://www.clamav.net/
- ImunifyAV: https://www.imunify360.com/antivirus

## 7. Contact

- Homepage: https://hostvn.vn , https://hostvn.net
- Group: hhttps://www.facebook.com/groups/hostvn.vn
- Email: Sanvv@hostvn.com

## 8. Feedback

- Due to lack of experience, the Scripts are difficult to avoid errors, I hope to receive your comments and contributions to make the Scripts better.
- Please send your feedback to sanvv@hostvn.com, Facebook group: https://www.facebook.com/groups/hostvn.vn or create Github Issues.

## 9. Contributors & Credits

### Developers / Maintainers
- Sanvv
- f97

### Contributors

