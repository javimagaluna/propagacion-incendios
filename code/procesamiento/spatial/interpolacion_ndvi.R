library(FNN)
library(sf)
library(dplyr)
library(terra)
library(gstat)


# LOAD DATA ---------------------------------------------------------------------
incendio = 'las_maquinas' # 'santa_ana'
carpeta = "data/procesado/"
path_NDVI <- paste0(carpeta, 'NDVI/', incendio, '_NDVI_points_v2.geojson')

ndvi <- read_sf(path_NDVI)
ndvi <- st_transform(ndvi, 32719)  
ndvi_prev <- ndvi %>% 
  filter(phase == 'PREVIO')  # 2017-01-09 al 2017-01-25 ... inicio incendio 20.


# func --------------------------------------------------------------------------

idw_knn_once <- function(src, dst, value_col, k=12, p=2, clamp=NULL){
  stopifnot(st_crs(src) == st_crs(dst))
  S <- st_coordinates(src)
  D <- st_coordinates(dst)
  v <- src[[value_col]]
  nn <- FNN::get.knnx(S, D, k=k)
  val <- numeric(nrow(dst))
  for(i in seq_len(nrow(dst))){
    idx <- nn$nn.index[i,]; dd <- nn$nn.dist[i,]; vv <- v[idx]
    z <- which(dd <= .Machine$double.eps)
    if(length(z)){
      val[i] <- vv[z[1]]
    } else {
      w <- 1/(dd^p); w <- w/sum(w)
      val[i] <- sum(w*vv)
    }
  }
  if(!is.null(clamp)){
    val <- pmin(pmax(val, clamp[1]), clamp[2])
  }
  val
}


# -----------------------------------------------------------------------------
## validacion cruzada para identificar k optimo
set.seed(2025)
K <- 5
ndvi_cv <- ndvi_prev
ndvi_cv$fold <- sample.int(K, nrow(ndvi_cv), replace = TRUE)

grid <- expand.grid(
  k = c(4, 6, 8, 10, 12, 16, 20),
  p = c(1.5, 2, 2.5)
)


cv_results <- lapply(seq_len(nrow(grid)), function(j){
  g  <- grid[j,]
  err <- c()
  for(f in 1:K){
    train <- ndvi_cv[ndvi_cv$fold != f, ]
    test  <- ndvi_cv[ndvi_cv$fold == f, ]
    preds <- idw_knn_once(train, test, "NDVI",
                          k = g$k, p = g$p,
                          clamp = c(-1, 1))
    err   <- c(err, preds - test$NDVI)
  }
  data.frame(
    k    = g$k,
    p    = g$p,
    RMSE = sqrt(mean(err^2, na.rm=TRUE)),
    MAE  = mean(abs(err), na.rm=TRUE)
  )
})

cv_results <- bind_rows(cv_results) %>%
  arrange(RMSE)

cv_results

#### ajustamos interpolacion

pred <- idw(
  NDVI ~ 1,
  as(ndvi_prev, "Spatial"),
  as(viirs_dem, "Spatial"),
  idp = 2.5,       # potencia
  nmax = 4         # k vecinos
)

## plots 
# fecha_filt <- "2023-01-29 06:36:00 -03"#"2017-01-20 18:00:00 -03"

# viirs %>% 
#   mutate(NDVI = pred$var1.pred) %>% 
#   filter(date_time == fecha_filt) %>% 
#   ggplot() +
#   geom_sf(aes(color = NDVI), size = 2, alpha = 0.7) +
#   theme_bw()+
#   scale_color_gradient2(
#     low = "brown",
#     mid = "yellow", 
#     high = "darkgreen",
#     midpoint = 0.3) +   # <0.3 pastos secos, sin o poca vegetacion
#   labs(color = "NDVI") 

# ndvi_prev %>% 
#   ggplot() +
#   geom_sf(aes(color = NDVI), size = 2, alpha = 0.7) +
#   theme_bw()+
#   scale_color_gradient2(
#     low = "brown",
#     mid = "yellow", 
#     high = "darkgreen",
#     midpoint = 0.3) +   # <0.3 pastos secos, sin o poca vegetacion
#   labs(color = "NDVI") 



viirs_era5 <- viirs_era5 %>% 
  mutate(NDVI_previo = pred$var1.pred)

viirs_4326 <- st_transform(viirs_dem, 4326)

viirs_xy <- viirs_4326 %>% 
  mutate(
    lon = st_coordinates(geometry)[,1],
    lat = st_coordinates(geometry)[,2]
  ) %>% 
  st_drop_geometry()

#write_parquet(viirs_xy, "data/input/viirs_era5_dem30_NDVI_las_maquinas.parquet")


### revision brillo:
viirs_4326 <- viirs_4326 %>% 
  rowwise() %>% 
  mutate(BT_I04 = calc_bt_planck(I04),
         BT_I05 = calc_bt_planck(I05, 11.45))

# fecha_filt = "2023-02-16 18:18:00 -03"

# viirs_4326 %>% 
#   filter(date_time == fecha_filt) %>% 
#   ggplot() +
#   geom_sf(aes(color = BT_I04), size = 2, alpha = 0.7) +
#   theme_bw()

viirs_xy <- viirs_4326 %>% 
  mutate(
    lon = st_coordinates(geometry)[,1],
    lat = st_coordinates(geometry)[,2]
  ) %>% 
  st_drop_geometry()

# write_parquet(viirs_xy, "data/input/viirs_era5_dem30_NDVI_BT_las_maquinas.parquet")

guardar_parquet(viirs_4326, "data/input/viirs_dem30_NDVI_BT_santa_ana.parquet")
