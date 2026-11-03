package com.example.wallpaperslideshow

import android.graphics.Bitmap
import android.graphics.ImageDecoder
import java.io.File
import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.roundToInt

object BitmapLoader {

    /**
     * 画像を指定サイズを覆う大きさに縮小して読み込み、中央で切り抜く(センタークロップ)。
     * ImageDecoder は EXIF の回転情報も反映してくれる。
     */
    fun loadCenterCrop(file: File, targetWidth: Int, targetHeight: Int): Bitmap {
        val decoded = decodeCovering(file, targetWidth, targetHeight)
        if (decoded.width == targetWidth && decoded.height == targetHeight) return decoded

        // 覆うサイズまで拡大(小さい画像の場合)してから中央を切り出す
        val scale = max(
            targetWidth.toFloat() / decoded.width,
            targetHeight.toFloat() / decoded.height
        )
        val scaled = if (scale > 1.001f) {
            Bitmap.createScaledBitmap(
                decoded,
                ceil(decoded.width * scale).toInt(),
                ceil(decoded.height * scale).toInt(),
                true
            ).also { if (it !== decoded) decoded.recycle() }
        } else {
            decoded
        }

        val w = minOf(targetWidth, scaled.width)
        val h = minOf(targetHeight, scaled.height)
        val x = (scaled.width - w) / 2
        val y = (scaled.height - h) / 2
        val cropped = Bitmap.createBitmap(scaled, x, y, w, h)
        if (cropped !== scaled) scaled.recycle()
        return cropped
    }

    /** サムネイル用:指定サイズ程度に縮小して読み込む */
    fun loadThumbnail(file: File, size: Int): Bitmap = decodeCovering(file, size, size)

    private fun decodeCovering(file: File, targetWidth: Int, targetHeight: Int): Bitmap {
        val source = ImageDecoder.createSource(file)
        return ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
            decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
            decoder.isMutableRequired = false
            val w = info.size.width
            val h = info.size.height
            val scale = max(targetWidth.toFloat() / w, targetHeight.toFloat() / h)
            if (scale < 1f) {
                decoder.setTargetSize(
                    max(1, (w * scale).roundToInt()),
                    max(1, (h * scale).roundToInt())
                )
            }
        }
    }
}
