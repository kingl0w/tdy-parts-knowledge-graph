# ---- stage 1: bulk-load the TTLs into a TDB2 database ----
FROM eclipse-temurin:21-jre AS builder

ARG JENA_VERSION=6.1.0
ENV JENA_HOME=/build/jena
WORKDIR /build

ADD https://archive.apache.org/dist/jena/binaries/apache-jena-${JENA_VERSION}.tar.gz /build/jena.tar.gz
RUN tar xzf jena.tar.gz && mv apache-jena-${JENA_VERSION} jena && rm jena.tar.gz

# the graph: asserted ontology, asserted data, HermiT-materialized inferences
COPY ontology/parts.ttl          /build/ttl/parts.ttl
COPY data/inventory.ttl          /build/ttl/inventory.ttl
COPY jena/reasoner/inferred.ttl  /build/ttl/inferred.ttl

RUN /build/jena/bin/tdb2.tdbloader --loc /data/tdyparts \
      /build/ttl/parts.ttl /build/ttl/inventory.ttl /build/ttl/inferred.ttl

# ---- stage 2: Fuseki serving the prebuilt store ----
FROM eclipse-temurin:21-jre AS runtime

ARG JENA_VERSION=6.1.0
WORKDIR /fuseki

ADD https://archive.apache.org/dist/jena/binaries/apache-jena-fuseki-${JENA_VERSION}.tar.gz /fuseki/fuseki.tar.gz
RUN tar xzf fuseki.tar.gz && mv apache-jena-fuseki-${JENA_VERSION} server && rm fuseki.tar.gz

COPY --from=builder /data/tdyparts /data/tdyparts
COPY jena/fuseki/tdyparts-docker.ttl /fuseki/config.ttl

EXPOSE 3030
CMD ["/fuseki/server/fuseki-server", "--config", "/fuseki/config.ttl"]
