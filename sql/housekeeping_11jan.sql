-- Count the number of fields in the edop_norm_ranges table (numerical fields)
SELECT COUNT(*) AS field_count
FROM information_schema.columns
WHERE table_name = 'edop_matrix'; -- 1566
--WHERE table_name = 'basin08'; -- 300
--WHERE table_name = 'edop_norm_ranges'; -- 63


select distinct feature_name from edop_pca_loadings; -- 122
select count(*) from gaz.wh2025 d;

