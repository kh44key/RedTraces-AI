CREATE DATABASE IF NOT EXISTS x_leaks_db;
CREATE DATABASE IF NOT EXISTS facebook_leaks_db;
CREATE DATABASE IF NOT EXISTS instagram_leaks_db;
GRANT ALL PRIVILEGES ON x_leaks_db.* TO 'pkcert'@'%';
GRANT ALL PRIVILEGES ON facebook_leaks_db.* TO 'pkcert'@'%';
GRANT ALL PRIVILEGES ON instagram_leaks_db.* TO 'pkcert'@'%';

CREATE DATABASE IF NOT EXISTS telegram_leaks_db;
GRANT ALL PRIVILEGES ON telegram_leaks_db.* TO 'pkcert'@'%';
