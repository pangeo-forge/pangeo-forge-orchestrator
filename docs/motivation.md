# Motivation

The first practical application of this package (even before we refactor other automation repos into it) is to orchestrate the process of generating STAC Items for datasets which have already been built with Pangeo Forge. All of the metadata required for cataloging already exists _somewhere_ in Pangeo Forge:

- the datasets themselves are in a Bakery target somewhere
- other metadata is available in the Feedstocks's `meta.yaml`

...so a generalizable cataloging approach needs to know:

- how to access a given Bakery target and open a dataset therein
- which datasets reside at which paths at the given Bakery target
- which Feedstocks (including Feedstock [version](https://github.com/pangeo-forge/roadmap/pull/34)) those paths were built from
- how to read/parse a `meta.yaml` from a given versioned Feedstock
