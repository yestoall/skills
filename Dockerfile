# The Linux check of nevera-recipes: a clean Debian with Node 22 (what
# `npx skills` needs) and nothing else the skill uses. docker/smoke.sh then
# runs the skill's own install steps and its tools on a real YouTube video.
#
#   docker build -t yestoall-skills-test . && docker run --rm yestoall-skills-test
FROM node:22-bookworm-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 sudo curl ca-certificates git \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /skills
COPY . .

CMD ["bash", "docker/smoke.sh"]
