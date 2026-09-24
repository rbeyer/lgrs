=========================
lgrs Usage in JavaScript
=========================

The *lgrs* library can run in a web browser, through
`Pyodide <https://pyodide.org>`__, which is a Python runtime compiled to
WebAssembly. The ``lgrs.js`` module wraps the most useful *lgrs* functions so
that JavaScript can call them. Wherever Python expects a number, ``lgrs.js``
also accepts a string (such as ``"0.0"``), and wherever possible it returns
JavaScript objects rather than Python objects.

This guide shows the essential calls. For complete, working web pages, see the
two files in the `examples folder
<https://github.com/rbeyer/lgrs/tree/master/examples>`__. Each marks its
*lgrs*-specific code with ``lgrs: BEGIN`` and ``lgrs: END`` comments. For
using *lgrs* from Python, see the `usage guide <usage.rst>`__.

.. note::

   Loading *lgrs* in a browser can take 10 seconds or more. Up to half that
   load time could be avoided by loading only those packages specifically
   needed by the web page, though grid generation would benefit less. That
   strategy is not yet implemented. If such a speedup would help your use
   case, please
   `open an issue <https://github.com/rbeyer/lgrs/issues/new?title=Faster+lgrs.js+loading>`__.


Loading lgrs
------------

Load the Pyodide script in your page with a ``<script>`` tag, then start
Python, install *lgrs*, and import ``lgrs.js``:

.. code-block:: html

    <script src="https://cdn.jsdelivr.net/pyodide/v314.0.1/full/pyodide.js"></script>

.. code-block:: javascript

    const pyodide = await loadPyodide();
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    await micropip.install("lgrs==X.Y.Z");
    const lgrsJs = pyodide.pyimport("lgrs.js");

Pin the *lgrs* version, as above (replace ``X.Y.Z`` with the release that you
want), so that a later release cannot change how your page behaves. The
remaining examples use the ``pyodide`` and ``lgrsJs`` objects created here.

Pyodide passes keyword arguments to a Python function through the
function's ``callKwargs()`` method, with the keyword arguments in a JavaScript
object as the last argument. The examples below use it wherever a function
takes keyword arguments. In the examples, a comment after a ``console.log()``
call shows what that call prints.


Converting a coordinate
-----------------------

Convert a coordinate (given as a string) to a related coordinate. The
``target`` argument names the result to return:

.. code-block:: javascript

    // Find the 1-m LGRS box that contains a geographic coordinate.
    const kwargs = { precision: 1, target: "nominal.lgrs.string" };
    const lgrsString = lgrsJs.convert_coordinate.callKwargs("80 N, 0 E", kwargs);
    console.log(lgrsString);  // ZA-0000022818

To get every related coordinate at once, set ``target`` to ``"json"`` and
``deserialize`` to ``true``, which returns a JavaScript object:

.. code-block:: javascript

    const kwargs = { precision: 1, target: "json", deserialize: true };
    const relatives = lgrsJs.convert_coordinate.callKwargs("80 N, 0 E", kwargs);
    console.log(relatives.nominal.lgrs);  // ZA-0000022818

Always specify ``target`` when you can. Without it, ``convert_coordinate()``
returns a JavaScript proxy of a Python object, and Pyodide never garbage
collects such proxies.


Making WKT
----------

Get the WKT definition of an LPS region or LTM zone by name or by components:

.. code-block:: javascript

    const wkt = lgrsJs.make_lunar_wkt("LTM 23N");
    console.log(wkt.split("\n")[0]);  // PROJCRS["Moon (2015) - Sphere / Ocentric / LTM 23N",

    // The same WKT, specified by component.
    const kwargs = { proj: "LTM", zone: 23, south: false };
    const sameWkt = lgrsJs.make_lunar_wkt.callKwargs(kwargs);
    console.log(sameWkt === wkt);  // true


Generating a grid
-----------------

``package_grid()`` generates a grid of LGRS (or ACC) boxes and either returns
it or offers it to the user as a downloaded .zip file. Specify the bounds
by component keywords, or by the name of an LPS region or LTM zone:

.. code-block:: javascript

    // Generate a grid of 100-m boxes. With no `out_name`, the grid is
    // returned as a JavaScript object rather than downloaded.
    const grid = lgrsJs.package_grid.callKwargs({
      left: 1, bottom: 1, right: 1.002, top: 1.002,
      crs: "IAU_2015:30100", precision: 100,
    });

    // The object has one property per CRS. Each property is a GeoJSON
    // FeatureCollection with one feature per box.
    console.log(Object.keys(grid));  // ["23N"]
    console.log(grid["23N"].features[0].properties.string);  // 23NGG052052

    // Generate a grid of 25-km boxes across all of LTM zone 23N.
    const zoneGrid = lgrsJs.package_grid.callKwargs({
      bounds: "23N", precision: 25000,
    });
    console.log(zoneGrid["23N"].features.length);  // 792

To download the grid instead, specify ``out_name``. The name follows the same
rules as the ``out_path`` argument of ``lgrs.easy.write_grid()``. The download
is a single .zip file that contains every output file:

.. code-block:: javascript

    // The browser downloads a file named grid.zip.
    lgrsJs.package_grid.callKwargs({
      bounds: "23N", precision: 25000, out_name: "grid.gpkg|layer={}",
    });


Using an HTML form
------------------

The ``convert_coordinate_from_form()`` and ``package_grid_from_form()``
functions read an HTML form directly, so a page needs no JavaScript to gather
the inputs:

.. code-block:: javascript

    const result = lgrsJs.convert_coordinate_from_form("conversion-form");

Each form element whose ``name`` matches an argument of
``convert_coordinate()`` supplies that argument. Checkboxes give ``true`` or
``false``, a group of radio buttons with the same name gives the value of the
checked button, and elements with any other name are ignored.
``package_grid_from_form()`` follows the same rules for the arguments of
``package_grid()``.


Handling errors
---------------

When a Python function raises an exception, JavaScript receives an error whose
``type`` property is the name of the Python exception class. Errors that come
from JavaScript itself have no ``type``. To read the Python message:

.. code-block:: javascript

    try {
      lgrsJs.convert_coordinate.callKwargs("not a coordinate", { precision: 1 });
    } catch (e) {
      if (e.type !== undefined) {
        const message = pyodide.runPython("import sys; str(sys.last_value)");
        console.error(e.type, message);
        // Prints: MalformedCoordinate `string` is not in a supported format:
        // 'not a coordinate'
      }
    }
