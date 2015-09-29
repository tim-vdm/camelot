Documentation can be read at:
    https://test-api.vortex-financials.be/api/docs

When tests pass locally but production doesn't work you can run locally from the egg:
    1. fab build -c ../conf/production.conf
    2. fab run_local -c ../conf/production.conf

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
