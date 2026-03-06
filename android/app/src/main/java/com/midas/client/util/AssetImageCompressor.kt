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
        val scaled = scaleBitmapIfNeeded(bitmap, MAX_IMAGE_SIDE_PX)
        if (scaled !== bitmap) {
            bitmap.recycle()
        }
        val output = ByteArrayOutputStream()
        val ok = scaled.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, output)
        scaled.recycle()
        if (!ok) {
            return null
        }
        val bytes = output.toByteArray()
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
