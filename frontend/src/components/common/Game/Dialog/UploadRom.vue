<script setup lang="ts">
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import RDialog from "@/components/common/RDialog.vue";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import { type Platform } from "@/stores/platforms";
import storeUpload from "@/stores/upload";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { xs, mdAndUp, smAndUp } = useDisplay();
const show = ref(false);
const filesToUpload = ref<File[]>([]);
const scanningStore = storeScanning();
const selectedPlatform = ref<Platform | null>(null);
const supportedPlatforms = ref<Platform[]>();
const heartbeat = storeHeartbeat();
const uploadStore = storeUpload();
const HEADERS = [
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "name",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showUploadRomDialog", (platformWhereUpload) => {
  if (platformWhereUpload) {
    selectedPlatform.value = platformWhereUpload;
  }
  show.value = true;
  platformApi
    .getSupportedPlatforms()
    .then(({ data }) => {
      supportedPlatforms.value = data.sort((a, b) => {
        return a.name.localeCompare(b.name);
      });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to upload roms: ${response?.data?.detail || response?.statusText || message}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
});

async function uploadRoms() {
  if (!selectedPlatform.value) return;
  show.value = false;

  if (selectedPlatform.value.id == -1) {
    await platformApi
      .uploadPlatform({ fsSlug: selectedPlatform.value.fs_slug })
      .then(({ data }) => {
        emitter?.emit("snackbarShow", {
          msg: `Platform ${selectedPlatform.value?.name} created successfully!`,
          icon: "mdi-check-bold",
          color: "green",
          timeout: 2000,
        });
        selectedPlatform.value = data;
      })
      .catch((error) => {
        console.log(error);
        emitter?.emit("snackbarShow", {
          msg: error.response.data.detail,
          icon: "mdi-close-circle",
          color: "red",
        });
        return;
      })
      .finally(() => {
        emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
      });
  }

  const platformId = selectedPlatform.value.id;

  await romApi
    .uploadRoms({
      filesToUpload: filesToUpload.value,
      platformId: platformId,
    })
    .then((responses: PromiseSettledResult<unknown>[]) => {
      const successfulUploads = responses.filter(
        (d) => d.status == "fulfilled",
      );
      const failedUploads = responses.filter((d) => d.status == "rejected");

      if (failedUploads.length == 0) {
        uploadStore.reset();
      }

      if (successfulUploads.length == 0) {
        return emitter?.emit("snackbarShow", {
          msg: `All files skipped, nothing to upload.`,
          icon: "mdi-close-circle",
          color: "orange",
          timeout: 5000,
        });
      }

      emitter?.emit("snackbarShow", {
        msg: `${successfulUploads.length} files uploaded successfully (and ${failedUploads.length} skipped/failed). Starting scan...`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 3000,
      });

      scanningStore.set(true);

      if (!socket.connected) socket.connect();
      setTimeout(() => {
        socket.emit("scan", {
          platforms: [platformId],
          type: "quick",
          apis: heartbeat.getEnabledMetadataOptions().map((s) => s.value),
        });
      }, 2000);
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to upload roms: ${response?.data?.detail || response?.statusText || message}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
  filesToUpload.value = [];
  selectedPlatform.value = null;
}

function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function removeRomFromList(romName: string) {
  filesToUpload.value = filesToUpload.value.filter(
    (rom) => rom.name !== romName,
  );
}

function closeDialog() {
  show.value = false;
  filesToUpload.value = [];
  selectedPlatform.value = null;
}
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-cloud-upload-outline"
    :width="mdAndUp ? '50vw' : '95vw'"
    scroll-content
  >
    <template #toolbar>
      <v-row class="align-center" no-gutters>
        <v-col cols="10" sm="8" lg="9">
          <v-autocomplete
            v-model="selectedPlatform"
            :label="t('common.platform')"
            item-title="name"
            :items="supportedPlatforms"
            return-object
            clearable
            single-line
            hide-details
          >
            <template #item="{ props, item }">
              <v-list-item
                class="py-2"
                v-bind="props"
                :title="item.raw.name ?? ''"
              >
                <template #prepend>
                  <platform-icon
                    :size="35"
                    :key="item.raw.slug"
                    :name="item.raw.name"
                    :slug="item.raw.slug"
                    :fs-slug="item.raw.fs_slug"
                  />
                </template>
              </v-list-item>
            </template>
            <template #selection="{ item }">
              <v-list-item class="px-0" :title="item.raw.name ?? ''">
                <template #prepend>
                  <platform-icon
                    :size="35"
                    :key="item.raw.slug"
                    :slug="item.raw.slug"
                    :name="item.raw.name"
                    :fs-slug="item.raw.fs_slug"
                  />
                </template>
              </v-list-item>
            </template>
          </v-autocomplete>
        </v-col>
        <v-col>
          <v-btn
            block
            icon=""
            class="text-primary bg-toplayer"
            variant="text"
            rounded="0"
            @click="triggerFileInput"
          >
            <v-icon :class="{ 'mr-2': !xs }"> mdi-plus </v-icon
            ><span v-if="!xs">{{ t("common.add") }}</span>
          </v-btn>
          <v-file-input
            id="file-input"
            v-model="filesToUpload"
            class="file-input"
            multiple
            required
          />
        </v-col>
      </v-row>
    </template>
    <template #content>
      <v-data-table-virtual
        v-if="filesToUpload.length > 0"
        :item-value="(item) => item.name"
        :items="filesToUpload"
        :width="mdAndUp ? '60vw' : '95vw'"
        :headers="HEADERS"
        hide-default-header
      >
        <template #item.name="{ item }">
          <v-list-item class="px-0">
            <v-row no-gutters>
              <v-col>
                {{ item.name }}
              </v-col>
            </v-row>
            <v-row no-gutters v-if="!smAndUp">
              <v-col>
                <v-chip size="x-small" label>{{
                  formatBytes(item.size)
                }}</v-chip>
              </v-col>
            </v-row>
            <template #append>
              <v-chip v-if="smAndUp" class="ml-2" size="x-small" label>{{
                formatBytes(item.size)
              }}</v-chip>
            </template>
          </v-list-item>
        </template>
        <template #item.actions="{ item }">
          <v-btn-group divided density="compact">
            <v-btn @click="removeRomFromList(item.name)">
              <v-icon class="text-romm-red"> mdi-close </v-icon>
            </v-btn>
          </v-btn-group>
        </template>
      </v-data-table-virtual>
    </template>
    <template #append>
      <v-divider />
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">{{
            t("common.cancel")
          }}</v-btn>
          <v-btn
            class="bg-toplayer text-romm-green"
            :disabled="filesToUpload.length == 0 || selectedPlatform == null"
            :variant="
              filesToUpload.length == 0 || selectedPlatform == null
                ? 'plain'
                : 'flat'
            "
            @click="uploadRoms"
          >
            {{ t("common.upload") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
