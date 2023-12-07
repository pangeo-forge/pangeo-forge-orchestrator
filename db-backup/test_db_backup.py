import os

from sqlmodel import Session, create_engine, select

from pangeo_forge_orchestrator.models import MODELS


def test_db_backup():
    database_url = os.environ["DATABASE_URL"]
    connect_args = dict(options="-c timezone=utc")
    engine = create_engine(database_url, echo=False, connect_args=connect_args)
    with Session(engine) as session:
        select_feedstocks = select(MODELS["feedstock"].table)
        feedstocks = session.exec(select_feedstocks).all()

        production_datasets = []
        for f in feedstocks:
            reciperun = MODELS["recipe_run"]
            select_datasets = select(reciperun.table).where(
                reciperun.table.feedstock_id == f.id,
                reciperun.table.dataset_public_url.isnot(None),
                reciperun.table.status == "completed",
                reciperun.table.conclusion == "success",
                reciperun.table.is_test.is_(False),
                reciperun.table.dataset_public_url.isnot(None),
            )
            dss = session.exec(select_datasets).all()
            production_datasets.append(dss)

    # some of these are empty lists, so drop those
    production_datasets = [dss for dss in production_datasets if dss]

    # get the list of dataset_public_urls
    dataset_public_urls = [ds.dataset_public_url for dss in production_datasets for ds in dss]

    # make sure it's the expected list of urls
    assert dataset_public_urls == [
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/noaa-coastwatch-geopolar-sst-feedstock/noaa-coastwatch-geopolar-sst.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/WOA_1degree_monthly-feedstock/woa18-1deg-monthly.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/cmip6-feedstock/test_surface.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/cmip6-feedstock/test_full_depth.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/cmip6-feedstock/CMIP6.CMIP.CCCma.CanESM5.historical.r1i1p1f1.Omon.zos.gn.v20190429.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/cmip6-feedstock/CMIP6.CMIP.CCCma.CanESM5.historical.r1i1p1f1.Omon.zos.gn.v20190429.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/cmip6-feedstock/CMIP6.DAMIP.NOAA-GFDL.GFDL-ESM4.hist-aer.r1i1p1f1.Amon.pr.gr1.v20180701.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/cmip6-feedstock/CMIP6.DAMIP.BCC.BCC-CSM2-MR.hist-aer.r1i1p1f1.Amon.pr.gn.v20190507.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/cmip6-feedstock/CMIP6.DAMIP.CCCma.CanESM5.hist-aer.r13i1p2f1.Amon.pr.gn.v20190429.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/cmip6-feedstock/CMIP6.DAMIP.CCCma.CanESM5.hist-aer.r10i1p1f1.Amon.pr.gn.v20190429.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/cmip6-feedstock/CMIP6.DAMIP.CCCma.CanESM5.hist-aer.r3i1p1f1.Amon.pr.gn.v20190429.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/cmip6-feedstock/CMIP6.PMIP.MPI-M.MPI-ESM1-2-LR.past2k.r1i1p1f1.Amon.tas.gn.v20210714.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/cmip6-feedstock/CMIP6.PMIP.MPI-M.MPI-ESM1-2-LR.past2k.r1i1p1f1.Amon.tas.gn.v20210714.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/CMIP6_static_grids-feedstock/NorESM2-LM.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/CMIP6_static_grids-feedstock/GFDL-ESM4.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/CMIP6_static_grids-feedstock/NorESM2-MM.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/CMIP6_static_grids-feedstock/MPI-ESM1-2-HR.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/CMIP6_static_grids-feedstock/MPI-ESM1-2-LR.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/CMIP6_static_grids-feedstock/NorESM2-MM.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/CMIP6_static_grids-feedstock/GFDL-ESM4.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/CMIP6_static_grids-feedstock/NorESM2-LM.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/CMIP6_static_grids-feedstock/MPI-ESM1-2-LR.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/CMIP6_static_grids-feedstock/MPI-ESM1-2-HR.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/CMIP6_static_grids-feedstock/MPI-ESM1-2-HR.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/gpcp-feedstock/gpcp.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/HadISST-feedstock/hadisst.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/AGDC-feedstock/AGCD.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/CMIP6-PMIP-feedstock/CMIP6.PMIP.MPI-M.MPI-ESM1-2-LR.past2k.r1i1p1f1.Amon.tas.gn.v20210714.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/CMIP6-PMIP-feedstock/CMIP6.PMIP.MRI.MRI-ESM2-0.past1000.r1i1p1f1.Amon.tas.gn.v20200120.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/CMIP6-PMIP-feedstock/CMIP6.PMIP.MIROC.MIROC-ES2L.past1000.r1i1p1f2.Amon.tas.gn.v20200318.zarr",
        "s3://yuvipanda-test1/cmr/gpm3imergdl.zarr/",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/eVolv2k-feedstock/eVolv2k.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/eVolv2k-feedstock/eVolv2k.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/LMRv2p1_MCruns_ensemble_gridded-feedstock/LMRv2p1_MCruns_ensemble_gridded.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/EOBS-feedstock/eobs-wind-speed.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/EOBS-feedstock/eobs-surface-downwelling.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/EOBS-feedstock/eobs-tg-tn-tx-rr-hu-pp.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/EOBS-feedstock/eobs-wind-speed.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/EOBS-feedstock/eobs-surface-downwelling.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/EOBS-feedstock/eobs-tg-tn-tx-rr-hu-pp.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/liveocean-feedstock/liveocean.zarr",
        "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/pangeo-forge/aws-noaa-oisst-feedstock/aws-noaa-oisst-avhrr-only.zarr",
    ]
