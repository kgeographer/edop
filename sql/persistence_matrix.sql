-- EDOP Persistence Matrix
  
CREATE OR REPLACE VIEW v_basin08_persist AS
select
  b.id,
  b.clz_cl_smj AS zone_id,
  z.genz_name  AS zone_name,      -- display field
  b.cls_cl_smj AS strata_id,
  s.gens_code  AS strata_code,    -- display field
  b.glc_cl_smj AS land_cover_id,
  g.glc_name   AS land_cover_name, -- display field
-- A: Physiographic Bedrock
	b.ele_mt_smn as elev_min,
	b.ele_mt_smx as elev_max,
	b.slp_dg_sav as slope_avg,
	b.slp_dg_uav as slope_upstream,
	b.sgr_dk_sav as stream_gradient,
	b.lit_cl_smj as lithology,
	l.class_name as	lith_class,
	b.kar_pc_sse as karst,
	b.kar_pc_use as karst_upstream,
-- B: Hydro-Climatic Baselines
	b.dis_m3_pyr as discharge_yr,
	b.dis_m3_pmn as discharge_min,
	b.dis_m3_pmx as discharge_max,
	b.ria_ha_ssu as river_area,
	b.ria_ha_usu as river_area_upstream,
	b.run_mm_syr as runoff,
	b.gwt_cm_sav as gw_table_depth,
	b.pnv_cl_smj as pnveg_id,
	p.pnv_name as pnv_majority,

	b.pnv_pc_s01 as pnveg_s01,
	
	b.pnv_pc_s02 as pnveg_s02,
	
	b.pnv_pc_s03 as pnveg_s03,
	
	b.pnv_pc_s01 as pnveg_s04,
	
	b.pnv_pc_s01 as pnveg_s05,
	
	b.pnv_pc_s01 as pnveg_s06,
	
	b.pnv_pc_s01 as pnveg_s07,
	
	b.pnv_pc_s01 as pnveg_s08,
	
	b.pnv_pc_s01 as pnveg_s09,
	
	b.pnv_pc_s01 as pnveg_s10,
	
	b.pnv_pc_s01 as pnveg_s11,
	
	b.pnv_pc_s01 as pnveg_s12,
	
	b.pnv_pc_s01 as pnveg_s13,
	
	b.pnv_pc_s01 as pnveg_s14,
	
	b.pnv_pc_s01 as pnveg_s15,
	
	b.cly_pc_sav as pct_clay,
	b.slt_pc_sav as pct_silt,
	b.snd_pc_sav as pct_sand,
-- C: Bioclimatic Proxies	
	b.tmp_dc_syr/10 as temp_yr,
	b.tmp_dc_smn/10 as temp_min,
	b.tmp_dc_smx/10 as temp_max,
	b.pre_mm_syr as precip_yr,
	b.ari_ix_sav as aridity,
	b.wet_pc_sg1 as wet_pct_grp2, -- group 1 ?
	b.wet_pc_sg2 as wet_pct_grp2, -- group 2 ?
	b.prm_pc_sse as permafrost_extent,
	b.tbi_cl_smj as biome_id,
	tb.biome_name as biome
	b.tec_cl_smj as eco_id,
	te.ecoregion_name as ecoregion
	b.fmh_cl_smj as freshwater_type,
	fm.mht_name AS freshwater_ecoregion_class,
	b.fec_cl_smj as freshwater_ecoreg,
	fe.ecoregion_name AS freshwater_ecoregion_name,
-- D: Anthropocene Markers
	b.rev_mc_usu as reservoir_vol,
	b.glc_cl_smj AS land_cover_id, -- spatial majority
	g.glc_name   AS land_cover_name, -- display field
	b.crp_pc_sse as cropland_extent,
	b.ppd_pk_sav AS pop_density,
	b.hft_ix_s09 as human_footprint_09,
	b.gdp_ud_sav as gdp_avg,
	b.hdi_ix_sav as human_dev_idx,
	b.geom
FROM public.basin08 b
LEFT JOIN public.lu_cls s
  ON s.gens_id = b.cls_cl_smj::varchar
LEFT JOIN public.lu_clz z
  ON z.genz_id = b.clz_cl_smj
LEFT JOIN public.lu_fec fe
  ON fe.eco_id = b.fec_cl_smj::varchar
LEFT JOIN public.lu_smj fm
  ON fm.mht_id = b.smj_cl_smj::varchar
LEFT JOIN public.lu_glc g
  ON g.glc_id = b.glc_cl_smj::varchar
LEFT JOIN public.lu_lit l
  ON l.glim_id = b.lit_cl_smj::varchar
LEFT JOIN public.lu_pnv p
  ON p.pnv_id = b.pnv_cl_smj
LEFT JOIN public.lu_tbi tb
  ON tb.glc_id = b.tbi_cl_smj::varchar
LEFT JOIN public.lu_tec te
  ON te.glc_id = b.tec_cl_smj::varchar
LEFT JOIN public.lu_wet w
  ON w.glc_id = b.wet_cl_smj::varchar
WHERE ST_Covers(
  b.geom,
  ST_SetSRID(ST_MakePoint(-3.00777252, 16.76618535), 4326)
)
ORDER BY ST_Area(b.geom::geography) ASC
LIMIT 1;
		
select * from v_basin08_persist;	
