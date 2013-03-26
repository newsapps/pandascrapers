#!/bin/bash
PROJECT=${HOME}/sites/pandascraper
RELEASE=${PROJECT}/repository

if [ -d "$WORKON_HOME" ]; then
    VIRTUAL_ENV=$WORKON_HOME/crime
else
    VIRTUAL_ENV=${HOME}/env
fi

source ${HOME}/.bash_profile
source $VIRTUAL_ENV/bin/activate

cd ${RELEASE}

echo "Warrant scraper started at `date`"
python ${RELEASE}/scrapers/warrant_import.py
echo "Warrant scraper finished at `date`"
