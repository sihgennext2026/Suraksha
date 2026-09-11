import { Directory, File, Paths } from 'expo-file-system';

import { CASE_MEDIA_DIRECTORY } from '@/constants/storage';
import type { CapturedImage } from '@/types';
import { createLogger } from '@/utils/logger';

const log = createLogger('media-store');

/**
 * Case imagery lives in the document directory, not the cache, so the operating
 * system cannot reclaim evidence for an unsynchronised case. Files are grouped
 * per case, which makes retention deletion a single directory removal.
 *
 * TODO(production): captures must be written through an encrypted container
 * keyed by the device keystore, and purged on the retention schedule set by the
 * unit's data policy.
 */
/** Which capture a file holds. One file per kind per case. */
export type CaptureKind = 'document' | 'document_back' | 'person';

export interface MediaStore {
  /** Moves a freshly captured image out of the cache into durable storage. */
  persistCapture(
    caseId: string,
    kind: CaptureKind,
    image: CapturedImage,
  ): Promise<CapturedImage>;
  /** Removes every image held for a case. Safe to call when none exist. */
  removeCaseMedia(caseId: string): Promise<void>;
  /** Total bytes held across all cases. Drives the storage read-out. */
  usedBytes(): Promise<number>;
  /** Fraction of device storage still free, 0..1. */
  availableFraction(): Promise<number>;
}

function rootDirectory(): Directory {
  return new Directory(Paths.document, CASE_MEDIA_DIRECTORY);
}

function caseDirectory(caseId: string): Directory {
  return new Directory(rootDirectory(), caseId);
}

function ensureDirectory(directory: Directory): void {
  if (!directory.exists) directory.create({ intermediates: true, idempotent: true });
}

class FileSystemMediaStore implements MediaStore {
  async persistCapture(
    caseId: string,
    kind: CaptureKind,
    image: CapturedImage,
  ): Promise<CapturedImage> {
    try {
      const directory = caseDirectory(caseId);
      ensureDirectory(directory);
      const source = new File(image.uri);
      if (!source.exists) return image;

      const extension = source.extension || '.jpg';
      const destination = new File(directory, `${kind}${extension}`);
      if (destination.exists) destination.delete();
      source.copy(destination);

      return { ...image, uri: destination.uri, sizeBytes: destination.size || image.sizeBytes };
    } catch (error) {
      // Persisting is an optimisation: the cached file is still readable for the
      // remainder of the session, so the screening can continue either way.
      log.warn('Could not persist capture; continuing with the cached file', {
        caseId,
        kind,
        ok: false,
      });
      void error;
      return image;
    }
  }

  async removeCaseMedia(caseId: string): Promise<void> {
    try {
      const directory = caseDirectory(caseId);
      if (directory.exists) directory.delete();
    } catch (error) {
      log.warn('Could not remove case media', { caseId, ok: false });
      void error;
    }
  }

  async usedBytes(): Promise<number> {
    try {
      const root = rootDirectory();
      if (!root.exists) return 0;
      return root.size ?? 0;
    } catch {
      return 0;
    }
  }

  async availableFraction(): Promise<number> {
    try {
      const total = Paths.totalDiskSpace;
      const available = Paths.availableDiskSpace;
      if (!total || total <= 0) return 1;
      return Math.min(1, Math.max(0, available / total));
    } catch {
      return 1;
    }
  }
}

export const mediaStore: MediaStore = new FileSystemMediaStore();
