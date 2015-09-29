#! /bin/sh

### BEGIN INIT INFO
# Provides:	aurora-serial
# Default-Start:	2 3 4 5
# Default-Stop:         0 1 6
# Required-Start:	$network $local_fs
# Required-Stop:	$network $local_fs
# Short-Description:	Aurora LED pattern generator (serial)
### END INIT INFO

set -e
umask 022

. /lib/lsb/init-functions


case "$1" in
  start)
  log_daemon_msg "Starting Aurora (serial)" "aurora-serial" || true
  if start-stop-daemon --start --quiet --oknodo --background --exec /home/pi/AuroraV6/aurora /dev/ttyACM0 ; then
    log_end_msg 0 || true
  else
    log_end_msg 1 || true
  fi
  ;;

  stop)
  log_daemon_msg "Stopping Aurora (serial)" "aurora-serial" || true
  if start-stop-daemon --stop --quiet --retry=TERM/30/KILL/5 --oknodo --exec /home/pi/AuroraV6/aurora; then
    log_end_msg 0 || true
  else
    log_end_msg 1 || true
  fi
  ;;

  status)
  status_of_proc /home/pi/AuroraV6/aurora aurora-serial && exit 0 || exit $?
  ;;

  *)
  log_action_msg "Usage: /etc/init.d/aurora-serial {start|stop|status}" || true
  exit 1
esac

exit 0
