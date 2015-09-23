Web Services - Test
===================

Currently, we are working on the Mock webservices and because we want to avoid to lose time with problems, there are two webservices where you can use them to debug your requests.

The `/request` web service will return all the information from your request, the HTTP header, the content-type and of course if your request is json compliant or not.

Test your HTTP request
----------------------

.. autoflask:: ws_server:create_app()
    :endpoints: api_test.debug_request

Your HTTP request is compliant
------------------------------

The `/is_compliant` web service will check if your request is compliant with the basic requirements of these services.



.. autoflask:: ws_server:create_app()
    :endpoints: api_test.is_compliant

