# EDOP: Environmental + Semantic Signatures for Historical Places

**Project goal**: Generate environmental signatures (from HydroATLAS/BasinATLAS data) and semantic signatures (from Wikipedia text embeddings) for historical places, enabling dual-signal similarity analysis.

**Progress so far**: 
- Built complete pipeline for 20 World Heritage sites: environmental PCA clustering + Wikipedia text harvesting/embedding across 4 semantic bands (history, environment, culture, modern)
- Scaled Wikipedia text pipeline to 258 World Heritage Cities (see `session_log_7Jan2026.md` for details)
- Generated embeddings and clusters for all 258 cities (stored in `output/corpus_258/`)

**Next steps**:
1. Add lon/lat coordinates to 258 WHC cities (user is reconciling to WHG, will provide coordinates file when ready)
2. Find basin_id for each city using spatial intersection with BasinATLAS level 08
3. Generate environmental signatures (PCA + clustering) for all 258 cities using same pipeline from 20-site pilot
4. Run cross-analysis comparing environmental vs. textual similarity measures

**Current state**: Text corpus complete, waiting for coordinates to proceed with environmental analysis.