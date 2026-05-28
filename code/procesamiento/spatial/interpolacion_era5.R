library(sf)
library(terra)
library(dplyr)
library(lubridate)
library(ggplot2)
library(arrow)
library(rnaturalearth)  ## para eliminar puntos del mar


# LOAD DATA -----------------------------------------------------------------
incendio = 'las_maquinas' # 'santa_ana'
carpeta = "data/procesado/"

path_viirs <- paste0(carpeta, 'satellite_data/union/suomi_', incendio, '.geojson')  # noaa1 para santa_ana
path_era5_variables <- paste0(carpeta, 'era5/era5_variables_', incendio, '_9km.geojson')

## load data viirs incendio:
viirs <- read_sf(path_viirs)

# identificacion zonas de agua --------------------
land <- ne_countries(scale = 50, returnclass = "sf") %>% st_union()
land_matching <- st_transform(land, st_crs(viirs))
viirs$en_tierra <- st_intersects(viirs, land_matching, sparse = FALSE)
table(viirs$en_tierra)

rm(land)
rm(land_matching)

### land para interpolacion
viirs <- st_transform(viirs, 32719)   # UTM19S Chile
viirs <- viirs %>%
  filter(en_tierra) %>%
  select(-en_tierra)


## load era5
era5 <- read_sf(path_era5_variables)


# func -----------------------------------------------------------

guardar_parquet <- function(sf_obj, file_path) {
  df_para_parquet <- sf_obj %>%
    st_drop_geometry()

  write_parquet(df_para_parquet, file_path)
}

# TEMPERATURA ----------------------------------------------------
#### LAS MAquinas
## AM
# 0.533719 24054.58
# 1.347301 25040.91
# 0.5166428 23894.28
# 0.8161143 24389.19

## PM
# 1.643075 17756.87  
# 3.669474 20987.94 
# 2.489667 19229.54 
# 4.95192 22047.03
# 3.175386 20246.02

variograma_AM_tem <- vgm(psill = 0.675, model = "Ste", range = 24220, nugget =  0.01, kappa = 10)
variograma_PM_tem <- vgm(psill = 3.2, model = "Ste", range = 20000, nugget = 0.01, kappa = 10)


#### SANTA ANA 
## AM
# Ste 0.7318841 23200.99    10
# Ste 0.5329395 21169    10
# Ste 0.4906308 21824.83    10
# Ste 0.710881 21880.46    10
# Ste 1.793638 27187.38    10

## PM
# Ste 2.791853 32184.77    10
# Ste 0.5565227 19668.65    10
# Ste 2.497436 30067.97    10
# Ste 3.68516 36130.12    10


variograma_AM_tem_santa_ana <- vgm(psill = 0.6165, model = "Ste", range = 22000, nugget =  0.01, kappa = 10)
variograma_PM_tem_santa_ana <- vgm(psill = 3, model = "Ste", range = 32800, nugget = 0.01, kappa = 10)


# HUMIDITY_PERCENT -------------------------------------

#### LAS MAquinaS
## AM autovariograma
# Ste 2.974646e+04 3583927  1
# Ste 29.16762 27779.04     5
# Ste 16.24502 41799.11     2
# Ste 16.09756 27584.15     5

## PM autovariograma
# Ste 12.22408 16031.02     5
# Ste 36.96285 21283.98     5
# Ste 15.17292917 18936.81  5
# Ste 23.37568 20249.86     5
# Ste 14.90662 19812.7      5

m_humedad_AM <- vgm(psill = 16.2, model = "Ste", range = 28000, nugget = 0.01, kappa = 5)
m_humedad_PM <- vgm(psill = 15.2, model = "Ste", range = 19800, nugget = 0.01, kappa = 5)


#### SANTA ANA 
## AM
# Ste 34.5067 34634.65    10
# Ste 56.66991 39135.77    10
# Ste 18.5658056 42916.55    10  # Ste 20.8460680 48131.16     5
# Ste 97.70703 43172.11    10
# Ste 3193.76771 368340.3    10

## PM RARO
# 1   Nug    1.301932      0.0     0
# 2   Ste 2643.935506 489953.3     5

# 1   Nug   0.4872974      0.0     0
# 2   Ste 285.9482404 327497.6     5

# 1   Nug   1.104192      0.0     0
# 2   Ste 567.513377 327329.1     5

# 1   Nug   2.631658      0.0     0
# 2   Ste 191.632535 172900.8     5

m_humedad_AM_santa_ana <- vgm(psill = 51.86236, model = "Ste", range = 40000, nugget = 0.01, kappa = 10)
m_humedad_PM_santa_ana <- vgm(psill = 348.3647, model = "Ste", range = 300000, nugget = 1.4, kappa = 5)


# V_COMPONENT_OF_WIND_10M -------------------------------------
#### LAS MAquinaS
## AM
# Ste 0.2445434 46673.37   0.9
# Ste 0.3110549 19148.63     5
# Ste 0.1669186 15073.89     5
# Ste 0.1597623 14923.81     5

## PM
# Ste 0.2813553 38117.54   1.2
# Ste 0.5310193 36993.67   1.6
# Ste 0.8546661 131898.5   0.7
# Ste 0.82409   69376.7    0.9
# Ste 0.1174452 14937.95     5

m_v_wind_AM <- vgm(psill = 0.17, model = "Ste", range = 15000, nugget = 0.02 * 0.17, kappa = 5)
m_v_wind_PM <- vgm(psill = 0.53, model = "Ste", range = 37000, nugget = 0.01, kappa = 1.5)


#### SANTA ANA 
## AM
# Ste 0.139261 15300.55    10
# Ste 0.09884357 12940.73    10
# Ste 0.08578922 14347.82    10
# Ste 0.4284107 19990.64    10
# Ste 0.06136421 13017.2    10

## PM
# Ste 0.5769116 31715.57    10
# Ste 0.1904898 18935.27    10
# Ste 0.31443081 26962.67    10
# Ste 0.06567748 11683.05    10


m_v_wind_AM_santa_ana  <- vgm(psill = 0.163, model = "Ste", range = 15000, nugget = 0.01, kappa = 10)
m_v_wind_PM_santa_ana  <- vgm(psill = 0.28, model = "Ste", range = 22300, nugget = 0.01, kappa = 10)


# u_component_of_wind_10m -------------------------------------
#### LAS MAquinaS
## AM
# Gau 0.3532896 20675.33
# Gau 0.245680649 21359.05
# Ste 0.3800529 23315.36    10
# Gau 0.3043193 21387.93

## PM
# Ste 1.246249 27315.2     5
# Ste 2.077251 27029.6    10
# Ste 1.032636 26859.5     5
# Ste 1.095177 26534.86    10
# Ste 1.06462 33241.4     2


m_u_wind_AM <- vgm(psill = 0.33, model = "Ste", range = 21300, nugget = 0.01, kappa = 8)
m_u_wind_PM <- vgm(psill = 1.1, model = "Ste", range = 27000, nugget = 0.01, kappa = 5)

#### SANTA ANA 
## AM
# Ste 0.8218865 44688.14    10
# Ste 0.4335944 34612.78    10
# Ste 0.3682927 31891.48    10
# Gau 8.63914135 149432.1
# Ste 1.063846 46659.47    10

## PM
# Ste 1.1724258398 30861.95    10
# Ste 4.302094 58504.79    10
# Gau 4.45498453 58819.22
# Ste 1.472169898 32743.25    10

m_u_wind_AM_santa_ana  <- vgm(psill = 0.67, model = "Ste", range = 39000, nugget = 0.01, kappa = 10)
m_u_wind_PM_santa_ana  <- vgm(psill = 2.2, model = "Ste", range = 45000, nugget = 0.01, kappa = 10)


# variograma para cada fecha -------------------------------------
resultados <- list()
fechas <- unique(viirs$date_time) %>% as.character()

for(fecha in fechas) {
  
  print(paste(fecha, '--------------------------------'))
  era5_filt_fecha <- era5 %>% 
    filter(date_time == fecha)
  print(era5_filt_fecha %>% nrow)
  
  viirs_filt <- viirs %>% 
    filter(date_time == fecha) 
  print(viirs_filt %>% nrow)
  
  puntos_sp <- as(viirs_filt, "Spatial")
  datos_sp <- as(era5_filt_fecha, "Spatial")
  
  date_f <- as.POSIXct(fecha, tz = "America/Santiago")
  hora <- as.numeric(format(date_f, "%H"))
  
  if(hora < 12) {
    print('variograma AM')
    v.fit <- variograma_AM_tem_santa_ana
    v_fit_humdedad <- m_humedad_AM_santa_ana
    v_fit_u_wind <- m_u_wind_AM_santa_ana
    v_fit_v_wind <- m_v_wind_AM_santa_ana
    
  }else{
    print('variograma PM')
    v.fit <- variograma_PM_tem_santa_ana
    v_fit_humdedad <- m_humedad_PM_santa_ana
    v_fit_u_wind <- m_u_wind_PM_santa_ana
    v_fit_v_wind <- m_v_wind_PM_santa_ana
  }
  
  ## temperature 
  print('obteniendo temperatura')
  krig <- krige(temperature_C ~ 1, datos_sp, puntos_sp, model = v.fit)
  viirs_filt$temperature_c_pred <- krig$var1.pred
  viirs_filt$temperature_c_var <- krig$var1.var
  
  ## humedad
  print('obteniendo humedad')
  krig <- krige(humidity_percent ~ 1, datos_sp, puntos_sp, model = v_fit_humdedad)
  viirs_filt$humidity_percent_pred <- krig$var1.pred
  viirs_filt$humidity_percent_var <- krig$var1.var
  
  ## u wind
  print('obteniendo u wind')
  krig <- krige(u_component_of_wind_10m ~ 1, datos_sp, puntos_sp, model = v_fit_u_wind)
  viirs_filt$u_wind_pred <- krig$var1.pred
  viirs_filt$u_wind_var <- krig$var1.var
  
  ## v wind
  print('obteniendo v wind')
  krig <- krige(v_component_of_wind_10m ~ 1, datos_sp, puntos_sp, model = v_fit_v_wind)
  viirs_filt$v_wind_pred <- krig$var1.pred
  viirs_filt$v_wind_var <- krig$var1.var
  
  
  resultados[[fecha]] <- viirs_filt
}


viirs_interpolado <- bind_rows(resultados)

viirs_interpolado <- viirs_interpolado %>%
  mutate(
    wind_speed_krig = sqrt(u_wind_pred ^2 + v_wind_pred ^2),
    wind_dir_krig  = (atan2(v_wind_pred, u_wind_pred) * 180 / pi) %% 360
  )

# transform and save data
viirs_4326 <- st_transform(viirs_interpolado, 4326)

# guardar_parquet(viirs_4326, 'data/input/viirs_interpolado_era5_las_maquinas.parquet')
# guardar_parquet(viirs_4326, 'data/input/viirs_era5_dem30_NDVI_BT_santa_ana.parquet')


## plot data ---------------------------------------------------------------------
# fecha_aux <- "2023-02-07 05:24:00"#"2017-01-31 17:54:00"
# viirs_interpolado %>% 
#   filter(date_time == fecha_aux) %>% 
#   as("Spatial") %>% 
#   spplot('I04')

# viirs_interpolado %>% 
#   filter(date_time == fecha_aux) %>% 
#   as("Spatial") %>% 
#   spplot('temperature_c_pred')

# viirs_interpolado %>% 
#   filter(date_time == fecha_aux) %>% 
#   as("Spatial") %>% 
#   spplot('humidity_percent_pred')

# viirs_interpolado %>% 
#   filter(date_time == fecha_aux) %>% 
#   as("Spatial") %>% 
#   spplot('wind_speed_krig')


