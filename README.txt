Documentation can be read at:
    https://test-api.vortex-financials.be/api/docs

To upload new version to production run:
    fab generate_hash -c ../conf/production.conf
    fab generate_db_file -c ../conf/production.conf
    fab -c ../conf/production.conf put_db_file:/path/to/ws/src/dir/tmp/generated.db
    fab build_upload -c ../conf/production.conf
    fab restart_service -c ../conf/production.conf

When tests pass locally but production doesn't work you can run locally from the egg:
    1. fab build -c ../conf/production.conf
    2. fab run_local -c ../conf/production.conf
    or
    1. cd dist/cloud
    2. export PYTHONPATH=../../../../v-finance/subrepos/cloudlaunch/
    3. python -m cloudlaunch.main --cld-file=v-finance-web-service-production.cld --cld-name=V-Finance-WS --cld-branch=production 8080

If we want to check the version, we have the check_hash command
    fab check_hash -c ../conf/production.conf

And if you want to generate this hash, just use
    fab generate_hash -c ../conf/production.conf
This command will create a hash file in the vfinance_ws/ directory, this file
will be packaged in the egg file with the build command.

For the developers, don't forget to add some environment variables
    DB_PATH=/tmp/test.db
    LOGHOME=/tmp/logs
    PYTHONPATH=/usr/local/lib/python2.7/site-packages:$HOME/v-finance-web-service/src

There is a conf/local.conf, you can use it for the run_local command

Documentation:

We use Sphinx for the documentation. 

```
cd docs/
make clean html
```

The result will be available in src/vfinance_ws/ws/docs/ and the webserver will
send the result to the browser when this one will check the last version of the
documentation.


To extract a separate schema and data file from the sqlite3 dump from VF:
```
sqlite3 <dump-filename> .sch > schema.sql
sqlite3 <dump-filename> .dump > dump.sql
grep -v -f schema.sql dump.sql > data.sql
```

