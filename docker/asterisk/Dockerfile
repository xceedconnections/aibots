FROM andrius/asterisk:latest

USER root
RUN mkdir -p /etc/asterisk /var/lib/asterisk/sounds /var/spool/asterisk

COPY conf/modules.conf /etc/asterisk/modules.conf
COPY conf/rtp.conf /etc/asterisk/rtp.conf
COPY conf/pjsip.conf /etc/asterisk/pjsip.conf
COPY conf/extensions.conf /etc/asterisk/extensions.conf
COPY conf/manager.conf /etc/asterisk/manager.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5060/udp 5060/tcp 5038 10000-10100/udp

ENTRYPOINT ["/entrypoint.sh"]
