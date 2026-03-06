package com.midas.client.util

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.provider.OpenableColumns
import java.io.ByteArrayOutputStream
import kotlin.math.max

data class CompressedImagePayload(
    val fileName: String,
    val bytes: ByteArray,
    val mimeType: String = "image/jpeg",
)

object AssetImageCompressor {
    private const val MAX_IMAGE_SIDE_PX = 1600
    private const val JPEG_QUALITY = 72
    private const val MIN_JPEG_QUALITY = 42
    private const val JPEG_QUALITY_STEP = 8
    private const val TARGET_MAX_BYTES = 450 * 1024
    private const val DOWNSCALE_FACTOR = 0.85f
    private const val MAX_DOWNSCALE_ROUNDS = 3
    private const val MIN_IMAGE_SIDE_PX = 640

    fun compressToJpeg(
        context: Context,
        uri: Uri,
        fallbackName: String,
    ): CompressedImagePayload? {
        val bounds = readBounds(context, uri) ?: return null
        val sampleSize = computeSampleSize(
            width = bounds.first,
            height = bounds.second,
            targetSide = MAX_IMAGE_SIDE_PX,
        )
        val bitmap = decodeBitmap(context, uri, sampleSize) ?: return null
        var scaled = scaleBitmapIfNeeded(bitmap, MAX_IMAGE_SIDE_PX)
        if (scaled !== bitmap) {
            bitmap.recycle()
        }

        var bestBytes: ByteArray? = null
        var round = 0
        while (round <= MAX_DOWNSCALE_ROUNDS) {
            val attempt = compressWithQualityFallback(scaled)
            if (attempt != null && attempt.isNotEmpty()) {
                bestBytes = attempt
                if (attempt.size <= TARGET_MAX_BYTES) {
                    break
                }
            }
            val longSide = max(scaled.width, scaled.height)
            if (longSide <= MIN_IMAGE_SIDE_PX) {
                break
            }
            val targetWidth = max((scaled.width * DOWNSCALE_FACTOR).toInt(), 1)
            val targetHeight = max((scaled.height * DOWNSCALE_FACTOR).toInt(), 1)
            val downscaled = Bitmap.createScaledBitmap(scaled, targetWidth, targetHeight, true)
            scaled.recycle()
            scaled = downscaled
            round += 1
        }
        scaled.recycle()
        val bytes = bestBytes ?: return null
        if (bytes.isEmpty()) {
            return null
        }
        val fileName = resolveDisplayName(context, uri)
            ?.let { ensureJpegSuffix(it) }
            ?: ensureJpegSuffix(fallbackName)
        return CompressedImagePayload(
            fileName = fileName,
            bytes = bytes,
            mimeType = "image/jpeg",
        )
    }

    private fun compressWithQualityFallback(bitmap: Bitmap): ByteArray? {
        var quality = JPEG_QUALITY
        var best: ByteArray? = null
        while (quality >= MIN_JPEG_QUALITY) {
            val bytes = compressJpeg(bitmap, quality) ?: return best
            best = bytes
            if (bytes.size <= TARGET_MAX_BYTES) {
                return bytes
            }
            quality -= JPEG_QUALITY_STEP
        }
        return best
    }

    private fun compressJpeg(bitmap: Bitmap, quality: Int): ByteArray? {
        val output = ByteArrayOutputStream()
        val ok = bitmap.compress(Bitmap.CompressFormat.JPEG, quality, output)
        if (!ok) {
            return null
        }
        return output.toByteArray()
    }

    private fun readBounds(context: Context, uri: Uri): Pair<Int, Int>? {
        val options = BitmapFactory.Options().apply {
            inJustDecodeBounds = true
        }
        context.contentResolver.openInputStream(uri).use { stream ->
            if (stream == null) {
                return null
            }
            BitmapFactory.decodeStream(stream, null, options)
        }
        if (options.outWidth <= 0 || options.outHeight <= 0) {
            return null
        }
        return options.outWidth to options.outHeight
    }

    private fun decodeBitmap(context: Context, uri: Uri, sampleSize: Int): Bitmap? {
        val options = BitmapFactory.Options().apply {
            inSampleSize = max(sampleSize, 1)
        }
        return context.contentResolver.openInputStream(uri).use { stream ->
            if (stream == null) {
                return null
            }
            BitmapFactory.decodeStream(stream, null, options)
        }
    }

    private fun computeSampleSize(width: Int, height: Int, targetSide: Int): Int {
        var sample = 1
        var currentWidth = width
        var currentHeight = height
        while (currentWidth > targetSide * 2 || currentHeight > targetSide * 2) {
            sample *= 2
            currentWidth /= 2
            currentHeight /= 2
        }
        return max(sample, 1)
    }

    private fun scaleBitmapIfNeeded(bitmap: Bitmap, targetSide: Int): Bitmap {
        val width = bitmap.width
        val height = bitmap.height
        val longSide = max(width, height)
        if (longSide <= targetSide) {
            return bitmap
        }
        val ratio = targetSide.toFloat() / longSide.toFloat()
        val targetWidth = max((width * ratio).toInt(), 1)
        val targetHeight = max((height * ratio).toInt(), 1)
        return Bitmap.createScaledBitmap(bitmap, targetWidth, targetHeight, true)
    }

    private fun resolveDisplayName(context: Context, uri: Uri): String? {
        val projection = arrayOf(OpenableColumns.DISPLAY_NAME)
        return context.contentResolver.query(uri, projection, null, null, null)
            ?.use { cursor ->
                val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index < 0 || !cursor.moveToFirst()) {
                    return@use null
                }
                cursor.getString(index)?.trim()?.takeIf { it.isNotBlank() }
            }
    }

    private fun ensureJpegSuffix(rawName: String): String {
        val name = rawName.trim()
        if (name.isBlank()) {
            return "asset_image.jpg"
        }
        val dotIndex = name.lastIndexOf('.')
        if (dotIndex <= 0) {
            return "$name.jpg"
        }
        val base = name.substring(0, dotIndex)
        val ext = name.substring(dotIndex + 1)
        val normalizedExt = ext.lowercase()
        return when (normalizedExt) {
            "jpg", "jpeg" -> name
            else -> "${base}.jpg"
        }
    }
}
