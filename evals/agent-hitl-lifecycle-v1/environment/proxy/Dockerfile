FROM alpine:3.22

RUN apk add --no-cache squid
COPY entrypoint.sh /usr/local/bin/benchmark-egress-proxy
RUN chmod 0555 /usr/local/bin/benchmark-egress-proxy

EXPOSE 3128
ENTRYPOINT ["/usr/local/bin/benchmark-egress-proxy"]
