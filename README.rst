====
lgrs
====


The lgrs package is software to support the Lunar Grid Reference System.

At the moment, this repo is under significant development and change as we
attempt to craft various pieces of code.  It is very messy and a work-in-process.
Nothing is guaranteed about structure until we pass the 1.0 version.




Installation
------------

Clone or download this repository.

It is highly suggested to install this into a virtual Python environment.

Change directory to where you have downloaded this repository after you have
set up your virtual environment, just do this::

$> pip install


or::

$> make install

If you use conda for your virtual environment and install dependencies via conda, you can do this::

$> conda create -n lgrs
$> conda activate lgrs
$> conda env update --file environment.yml
$> pip install --no-deps .


Contributing
------------

Feedback, issues, and contributions are always gratefully welcomed. See the
contributing guide for details on how to help and setup a development
environment.


Credits
-------

lgrs was developed in the open at the SETI Institute, based on open code originally 
developed by the United States Geological Survey.

See the `AUTHORS <https://github.com/rbeyer/lgrs/blob/master/AUTHORS.rst>`
file for a complete list of developers.


License
-------
The "lgrs" software is licensed under the Apache License,
Version 2.0 (the "License"); you may not use this file except in
compliance with the License. You may obtain a copy of the License
at http://www.apache.org/licenses/LICENSE-2.0.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied. See the License for the specific language governing
permissions and limitations under the License.
